import asyncio
import time
from typing import Dict, Optional
from astream.config.app_settings import settings
from astream.utils.logger import logger


class RateLimiter:
    """Rate limiter par IP pour éviter surcharge d'anime-sama."""
    
    def __init__(self):
        self._last_request_times: Dict[str, float] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
    
    async def wait_if_needed(self, client_ip: str, delay: Optional[float] = None) -> None:
        """Attend si nécessaire pour respecter le rate limiting par IP."""
        if delay is None:
            delay = settings.RATE_LIMIT_PER_USER
            
        if delay <= 0:
            return
        
        if client_ip not in self._locks:
            self._locks[client_ip] = asyncio.Lock()
        
        async with self._locks[client_ip]:
            current_time = time.time()
            last_request = self._last_request_times.get(client_ip, 0)
            
            time_since_last = current_time - last_request
            
            if time_since_last < delay:
                wait_time = delay - time_since_last
                logger.log("PERFORMANCE", f"Rate limiting IP {client_ip}: attente {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
            
            self._last_request_times[client_ip] = time.time()
    


rate_limiter = RateLimiter()