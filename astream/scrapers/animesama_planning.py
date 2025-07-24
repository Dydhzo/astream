import re
from typing import List, Set
from astream.utils.logger import logger
from astream.utils.base_scraper import BaseScraper
from astream.utils.database import get_metadata_from_cache, set_metadata_to_cache
from astream.config.app_settings import settings


class AnimeSamaPlanning(BaseScraper):
    """Vérifie le planning pour déterminer les animes en cours."""
    
    def __init__(self, client):
        super().__init__(client, "https://anime-sama.fr")
        self.planning_url = "https://anime-sama.fr/planning/"
    
    async def get_current_planning_animes(self) -> Set[str]:
        """Récupère les animes actuellement dans le planning."""
        cached_planning = await get_metadata_from_cache("as:anime_planning")
        if cached_planning:
            logger.debug(f"⚡ PERFORMANCE: Planning récupéré depuis le cache")
            return set(cached_planning.get("anime_slugs", []))
        
        logger.info(f"🐍 ANIMESAMA: Scraping du planning en cours")
        try:
            response = await self._rate_limited_request('get', self.planning_url)
            if not response:
                logger.warning("🐍 ANIMESAMA: Impossible de récupérer le planning")
                return set()
            
            anime_slugs = self._extract_anime_slugs_from_planning(response.text)
            
            planning_data = {"anime_slugs": list(anime_slugs)}
            await set_metadata_to_cache(
                "as:anime_planning", 
                planning_data, 
                settings.PLANNING_CACHE_TTL
            )
            
            logger.info(f"🐍 ANIMESAMA: Planning mis à jour: {len(anime_slugs)} animes actifs")
            return anime_slugs
            
        except Exception as e:
            logger.error(f"🐍 ANIMESAMA: Erreur scraping planning: {e}")
            return set()
    
    def _extract_anime_slugs_from_planning(self, html_content: str) -> Set[str]:
        """Extrait les slugs d'animes depuis le JavaScript du planning."""
        anime_slugs = set()
        
        try:
            pattern = r'cartePlanningAnime\([^,]+,\s*"([^"]+)"'
            matches = re.findall(pattern, html_content)
            
            for url_path in matches:
                slug = url_path.split('/')[0]
                if slug:
                    anime_slugs.add(slug)
            
            logger.debug(f"🔍 DEBUG: Slugs planning extraits: {sorted(anime_slugs)}")
            
        except Exception as e:
            logger.error(f"🐍 ANIMESAMA: Erreur extraction slugs planning: {e}")
        
        return anime_slugs
    
    async def is_anime_ongoing(self, anime_slug: str) -> bool:
        """Vérifie si un anime est en cours selon le planning."""
        current_planning = await self.get_current_planning_animes()
        
        is_ongoing = (
            anime_slug in current_planning or
            any(slug.startswith(anime_slug) for slug in current_planning) or
            any(anime_slug.startswith(slug) for slug in current_planning)
        )
        
        status = "EN COURS" if is_ongoing else "TERMINÉ"
        logger.debug(f"🔍 DEBUG: Anime '{anime_slug}': {status}")
        
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
            logger.debug(f"⚡ PERFORMANCE: TTL anime EN COURS '{anime_slug}': {ttl}s")
        else:
            ttl = settings.FINISHED_ANIME_TTL  
            logger.debug(f"⚡ PERFORMANCE: TTL anime TERMINÉ '{anime_slug}': {ttl}s")
        
        return ttl
        
    except Exception as e:
        logger.warning(f"⚡ PERFORMANCE: Erreur calcul TTL '{anime_slug}': {e}")
        return settings.ONGOING_ANIME_TTL