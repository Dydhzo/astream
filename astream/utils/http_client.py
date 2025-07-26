import httpx
import asyncio
import random
from urllib.parse import urlparse

from astream.config.app_settings import settings
from astream.utils.logger import logger


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


def should_bypass_proxy(url: str) -> bool:
    """Vérifie si une URL doit bypasser le proxy selon PROXY_BYPASS_DOMAINS."""
    if not settings.PROXY_URL or not settings.PROXY_BYPASS_DOMAINS:
        return False
    
    try:
        domain = urlparse(url).netloc.lower()
        bypass_domains = [d.strip().lower() for d in settings.PROXY_BYPASS_DOMAINS.split(',') if d.strip()]
        
        for bypass_domain in bypass_domains:
            if bypass_domain in domain:
                logger.log("PROXY", f"Bypass proxy pour {domain} (règle: {bypass_domain})")
                return True
        
        return False
    except Exception as e:
        logger.log("WARNING", f"Erreur vérification bypass proxy: {e}")
        return False


class BaseClient:
    """Classe de base pour les clients avec fermeture asynchrone."""
    
    def __init__(self):
        self.client = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def close(self):
        """Ferme les clients et nettoie les ressources."""
        # Fermer le client proxy
        if hasattr(self, 'proxy_client') and self.proxy_client:
            if hasattr(self.proxy_client, 'close'):
                await self.proxy_client.close()
            elif hasattr(self.proxy_client, 'aclose'):
                await self.proxy_client.aclose()
            self.proxy_client = None
        
        # Fermer le client direct (seulement si différent du proxy)
        if hasattr(self, 'direct_client') and self.direct_client and self.direct_client != self.proxy_client:
            if hasattr(self.direct_client, 'close'):
                await self.direct_client.close()
            elif hasattr(self.direct_client, 'aclose'):
                await self.direct_client.aclose()
            self.direct_client = None
        
        # Nettoyer la référence du client par défaut
        self.client = None


class HttpClient(BaseClient):
    """Client HTTP unifié avec tentatives automatiques et bypass proxy."""
    
    def __init__(self, base_url: str = "", timeout: float = None, retries: int = 3):
        if timeout is None:
            timeout = settings.HTTP_TIMEOUT
        super().__init__()
        self.base_url = base_url
        self.timeout = timeout
        self.retries = retries
        self.proxy_client = None  # Client avec proxy
        self.direct_client = None  # Client sans proxy
        self._setup_clients()
    
    def _setup_clients(self):
        """Configure les clients HTTP avec et sans proxy."""
        headers = get_default_headers()
        base_config = {
            "timeout": httpx.Timeout(self.timeout),
            "headers": headers,
            "follow_redirects": True
        }
        
        # Client direct (sans proxy)
        self.direct_client = httpx.AsyncClient(**base_config)
        
        # Client avec proxy si configuré
        if settings.PROXY_URL:
            proxy_config = base_config.copy()
            proxy_config["proxy"] = settings.PROXY_URL
            self.proxy_client = httpx.AsyncClient(**proxy_config)
            logger.log("INFO", f"Configuration du proxy: {settings.PROXY_URL}")
        else:
            self.proxy_client = self.direct_client
        
        # Client par défaut
        self.client = self.proxy_client
    
    def _get_client_for_url(self, url: str) -> httpx.AsyncClient:
        """Retourne le client approprié selon l'URL et les règles de bypass."""
        if should_bypass_proxy(url):
            return self.direct_client
        else:
            return self.proxy_client
    
    @property
    def is_closed(self) -> bool:
        """Vérifie si les clients sont fermés."""
        proxy_closed = self.proxy_client is None or self.proxy_client.is_closed
        direct_closed = self.direct_client is None or self.direct_client.is_closed
        return proxy_closed and direct_closed
    
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
        
        # Correction vidmoly.to → moly.to (insensible à la casse)
        if "vidmoly.to" in url.lower():
            import re
            url = re.sub(r'vidmoly\.to', 'moly.to', url, flags=re.IGNORECASE)
        
        # Sélectionner le client approprié selon l'URL
        client = self._get_client_for_url(url)
        last_exception = None
        
        for attempt in range(self.retries):
            try:
                if self.is_closed:
                    self._setup_clients()
                    client = self._get_client_for_url(url)
                
                bypass_info = " (bypass proxy)" if client is self.direct_client and settings.PROXY_URL else ""
                logger.log("API", f"{method} {url}{bypass_info} (tentative {attempt + 1}/{self.retries})")
                
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                
                logger.log("API", f"{method} {url} → {response.status_code}")
                return response
                
            except httpx.TimeoutException as e:
                last_exception = e
                logger.log("WARNING", f"{method} {url} timeout (tentative {attempt + 1}/{self.retries})")
                if attempt < self.retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                    
            except httpx.HTTPStatusError as e:
                last_exception = e
                if e.response.status_code >= 500:
                    logger.log("WARNING", f"{method} {url} → {e.response.status_code} (tentative {attempt + 1}/{self.retries})")
                    if attempt < self.retries - 1:
                        await asyncio.sleep(1 * (attempt + 1))
                        continue
                else:
                    logger.log("ERROR", f"{method} {url} → {e.response.status_code}")
                    raise
                    
            except Exception as e:
                last_exception = e
                logger.log("ERROR", f"{method} {url} erreur: {str(e)} (tentative {attempt + 1}/{self.retries})")
                if attempt < self.retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))
        
        logger.log("ERROR", f"{method} {url} a échoué après {self.retries} tentatives")
        if last_exception:
            raise last_exception
        else:
            raise httpx.RequestError(f"La requête a échoué après {self.retries} tentatives")
