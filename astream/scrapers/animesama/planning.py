import re
from typing import List, Set
from astream.utils.logger import logger
from astream.scrapers.base import BaseScraper
from astream.utils.data.database import get_metadata_from_cache, set_metadata_to_cache
from astream.config.settings import settings


class AnimeSamaPlanning(BaseScraper):
    """Vérifie le planning pour déterminer les anime en cours."""
    
    def __init__(self, client):
        super().__init__(client, settings.ANIMESAMA_URL)
        self.planning_url = f"{settings.ANIMESAMA_URL}/planning/"
    
    async def get_current_planning_anime(self) -> Set[str]:
        """Récupère les anime actuellement dans le planning."""
        cached_planning = await get_metadata_from_cache("as:planning")
        if cached_planning:
            logger.log("PERFORMANCE", f"Planning récupéré depuis le cache")
            return set(cached_planning.get("anime_slugs", []))
        
        logger.log("ANIMESAMA", f"Scraping du planning en cours")
        try:
            response = await self._rate_limited_request('get', self.planning_url)
            if not response:
                logger.warning("ANIMESAMA: Impossible de récupérer le planning")
                return set()
            
            anime_slugs = self._extract_anime_slugs_from_planning(response.text)
            
            planning_data = {"anime_slugs": list(anime_slugs)}
            await set_metadata_to_cache(
                "as:planning", 
                planning_data, 
                settings.PLANNING_TTL
            )
            
            logger.log("ANIMESAMA", f"Planning mis à jour: {len(anime_slugs)} anime actifs")
            return anime_slugs
            
        except Exception as e:
            logger.error(f"ANIMESAMA: Erreur scraping planning: {e}")
            return set()
    
    def _extract_anime_slugs_from_planning(self, html_content: str) -> Set[str]:
        """Extrait les slugs d'anime depuis le JavaScript du planning."""
        anime_slugs = set()
        
        try:
            pattern = r'cartePlanningAnime\([^,]+,\s*"([^"]+)"'
            matches = re.findall(pattern, html_content)
            
            for url_path in matches:
                slug = url_path.split('/')[0]
                if slug:
                    anime_slugs.add(slug)
            
            logger.debug(f"Slugs planning extraits: {sorted(anime_slugs)}")
            
        except Exception as e:
            logger.error(f"ANIMESAMA: Erreur extraction slugs planning: {e}")
        
        return anime_slugs
    
    async def is_anime_ongoing(self, anime_slug: str) -> bool:
        """Vérifie si un anime est en cours selon le planning."""
        current_planning = await self.get_current_planning_anime()
        
        is_ongoing = (
            anime_slug in current_planning or
            any(slug.startswith(anime_slug) for slug in current_planning) or
            any(anime_slug.startswith(slug) for slug in current_planning)
        )
        
        status = "EN COURS" if is_ongoing else "TERMINÉ"
        logger.debug(f"Anime '{anime_slug}': {status}")
        
        return is_ongoing


_planning_checker = None

async def get_planning_checker():
    """Retourne l'instance globale du vérificateur."""
    global _planning_checker
    if _planning_checker is None:
        from astream.utils.dependencies import get_animesama_api
        api = await get_animesama_api()
        _planning_checker = AnimeSamaPlanning(api.client)
    return _planning_checker


async def is_anime_ongoing(anime_slug: str) -> bool:
    """Vérifie si un anime est en cours."""
    checker = await get_planning_checker()
    return await checker.is_anime_ongoing(anime_slug)


async def get_smart_cache_ttl(anime_slug: str) -> int:
    """Calcule le TTL intelligent selon le statut de l'anime."""
    try:
        if await is_anime_ongoing(anime_slug):
            ttl = settings.ONGOING_ANIME_TTL
            logger.log("PERFORMANCE", f"TTL anime EN COURS '{anime_slug}': {ttl}s")
        else:
            ttl = settings.FINISHED_ANIME_TTL  
            logger.log("PERFORMANCE", f"TTL anime TERMINÉ '{anime_slug}': {ttl}s")
        
        return ttl
        
    except Exception as e:
        logger.warning(f"PERFORMANCE: Erreur calcul TTL '{anime_slug}': {e}")
        return settings.ONGOING_ANIME_TTL