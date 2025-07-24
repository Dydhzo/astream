import logging
import httpx
import asyncio
import random

from astream.config.app_settings import settings


USER_AGENT_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
]

def get_random_user_agent():
    """Retourne un User-Agent aléatoire depuis le pool."""
    return random.choice(USER_AGENT_POOL)

def get_default_headers():
    """Génère des headers de base avec User-Agent aléatoire."""
    return {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Cache-Control": "max-age=0",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive",
    }

def get_sibnet_headers(referer_url):
    """Génère des headers spéciaux pour Sibnet avec User-Agent aléatoire."""
    return {
        "User-Agent": get_random_user_agent(),
        "Referer": referer_url,
        "Accept": "*/*",
        "Range": "bytes=0-",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive"
    }


class BaseClient:
    """Classe de base pour les clients avec fermeture asynchrone."""
    
    def __init__(self):
        self.client = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def close(self):
        """Ferme le client et nettoie les ressources."""
        if hasattr(self, 'client') and self.client:
            if hasattr(self.client, 'close'):
                await self.client.close()
            elif hasattr(self.client, 'aclose'):
                await self.client.aclose()
            self.client = None


class HttpClient(BaseClient):
    """Client HTTP unifié avec tentatives automatiques."""
    
    def __init__(self, base_url: str = "", timeout: float = None, retries: int = 3):
        if timeout is None:
            timeout = settings.HTTP_TIMEOUT
        super().__init__()
        self.base_url = base_url
        self.timeout = timeout
        self.retries = retries
        self.logger = logging.getLogger(f"http_client.{base_url}")
        self._setup_client()
    
    def _setup_client(self):
        """Configure le client HTTP avec les options appropriées."""
        headers = get_default_headers()
        
        proxy_config = {}
        if settings.PROXY_URL:
            proxy_config = {"proxy": settings.PROXY_URL}
            self.logger.info(f"📊 INFO: Configuration du proxy: {settings.PROXY_URL}")
        
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            headers=headers,
            follow_redirects=True,
            **proxy_config
        )
    
    @property
    def is_closed(self) -> bool:
        """Vérifie si le client est fermé."""
        return self.client is None or self.client.is_closed
    
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """Effectue une requête GET avec nouvelles tentatives automatiques."""
        return await self._request("GET", url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> httpx.Response:
        """Effectue une requête POST avec nouvelles tentatives automatiques."""
        return await self._request("POST", url, **kwargs)
    
    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Effectue une requête HTTP avec tentatives et gestion d'erreurs."""
        if not url.startswith('http'):
            url = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"
        
        last_exception = None
        
        for attempt in range(self.retries):
            try:
                if self.is_closed:
                    self._setup_client()
                
                self.logger.debug(f"📁 API: {method} {url} (tentative {attempt + 1}/{self.retries})")
                
                response = await self.client.request(method, url, **kwargs)
                response.raise_for_status()
                
                self.logger.debug(f"📁 API: {method} {url} → {response.status_code}")
                return response
                
            except httpx.TimeoutException as e:
                last_exception = e
                self.logger.warning(f"⚠️ WARNING: {method} {url} timeout (tentative {attempt + 1}/{self.retries})")
                if attempt < self.retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                    
            except httpx.HTTPStatusError as e:
                last_exception = e
                if e.response.status_code >= 500:
                    self.logger.warning(f"⚠️ WARNING: {method} {url} → {e.response.status_code} (tentative {attempt + 1}/{self.retries})")
                    if attempt < self.retries - 1:
                        await asyncio.sleep(1 * (attempt + 1))
                        continue
                else:
                    self.logger.error(f"❌ ERROR: {method} {url} → {e.response.status_code}")
                    raise
                    
            except Exception as e:
                last_exception = e
                self.logger.error(f"❌ ERROR: {method} {url} erreur: {str(e)} (tentative {attempt + 1}/{self.retries})")
                if attempt < self.retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))
        
        self.logger.error(f"❌ ERROR: {method} {url} a échoué après {self.retries} tentatives")
        if last_exception:
            raise last_exception
        else:
            raise httpx.RequestError(f"La requête a échoué après {self.retries} tentatives")
