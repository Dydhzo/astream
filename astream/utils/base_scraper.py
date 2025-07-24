from abc import ABC
from typing import Any, Dict, Optional

from astream.utils.http_client import HttpClient
from astream.utils.logger import logger
from astream.utils.rate_limiter import rate_limiter


class BaseScraper(ABC):
    """Classe de base pour scrapers avec fonctionnalités HTTP communes."""
    
    def __init__(self, client: HttpClient, base_url: str):
        self.client = client
        self.base_url = base_url
        self._current_client_ip: Optional[str] = None
    
    def set_client_ip(self, client_ip: str) -> None:
        """Définit l'IP du client pour le rate limiting."""
        self._current_client_ip = client_ip
    
    async def _rate_limited_request(self, method: str, url: str, **kwargs) -> Any:
        """Effectue une requête avec rate limiting."""
        if self._current_client_ip:
            await rate_limiter.wait_if_needed(self._current_client_ip)
        
        logger.debug(f"📁 API: Rate limited request {method.upper()} {url}", extra={
            "client_ip": self._current_client_ip,
            "method": method,
            "url": url
        })
        
        return await self._execute_request(method, url, **kwargs)
    
    async def _internal_request(self, method: str, url: str, **kwargs) -> Any:
        """Effectue une requête interne SANS rate limiting (pour détection parallèle)."""
        logger.debug(f"📁 API: Internal request {method.upper()} {url}", extra={
            "method": method,
            "url": url
        })
        
        return await self._execute_request(method, url, **kwargs)
    
    async def _execute_request(self, method: str, url: str, **kwargs) -> Any:
        """Exécute la requête HTTP selon la méthode spécifiée."""
        method_lower = method.lower()
        
        if method_lower == 'get':
            return await self.client.get(url, **kwargs)
        elif method_lower == 'post':
            return await self.client.post(url, **kwargs)
        elif method_lower == 'put':
            return await self.client.put(url, **kwargs)
        elif method_lower == 'delete':
            return await self.client.delete(url, **kwargs)
        else:
            raise ValueError(f"Méthode HTTP non supportée: {method}")