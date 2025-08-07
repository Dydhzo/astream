from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup

from astream.utils.http.client import HttpClient
from astream.utils.logger import logger
from astream.scrapers.base import BaseScraper
from astream.utils.data.database import get_metadata_from_cache, set_metadata_to_cache, DistributedLock, LockAcquisitionError
from astream.config.settings import settings
from astream.scrapers.animesama.parser import (
    parse_anime_details_from_html,
    parse_languages_from_html,
    parse_seasons_from_html,
    parse_film_titles_from_html
)


class AnimeSamaDetails(BaseScraper):
    """Gestionnaire des détails d'anime AnimeSama."""
    
    def __init__(self, client: HttpClient):
        super().__init__(client, settings.ANIMESAMA_URL)

    async def get_anime_details(self, anime_slug: str) -> Optional[Dict[str, Any]]:
        """Récupère les détails d'un anime par slug."""
        try:
            logger.debug(f"ANIMESAMA: Récupération détails pour {anime_slug}")
            response = await self._rate_limited_request('get', f"{self.base_url}/catalogue/{anime_slug}/")
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            anime_data = parse_anime_details_from_html(soup, anime_slug)
            
            anime_data["languages"] = parse_languages_from_html(response.text)
            
            return anime_data
            
        except Exception as e:
            logger.error(f"ANIMESAMA: Échec détails pour {anime_slug}: {e}")
            return None

    async def get_seasons(self, anime_slug: str) -> List[Dict[str, Any]]:
        """Récupère les saisons disponibles."""
        try:
            logger.debug(f"ANIMESAMA: Récupération saisons pour {anime_slug}")
            response = await self._rate_limited_request('get', f"{self.base_url}/catalogue/{anime_slug}/")
            response.raise_for_status()
            
            seasons = parse_seasons_from_html(response.text, anime_slug, self.base_url)
            return seasons
            
        except Exception as e:
            logger.error(f"ANIMESAMA: Échec saisons pour {anime_slug}: {e}")
            return []

    async def get_film_title(self, anime_slug: str, episode_num: int) -> Optional[str]:
        """Récupère le titre d'un film."""
        try:
            film_url = f"{self.base_url}/catalogue/{anime_slug}/film/vostfr/"
            
            response = await self._internal_request('get', film_url)
            response.raise_for_status()
            html = response.text
            
            film_titles = parse_film_titles_from_html(html)
            
            logger.debug(f"Titres films trouvés: {film_titles}")
            
            if episode_num <= len(film_titles):
                film_title = film_titles[episode_num - 1].strip()
                logger.debug(f"Titre film sélectionné: '{film_title}'")
                return film_title
            else:
                logger.warning(f"Épisode #{episode_num} > nombre films ({len(film_titles)})")
                return None
                
        except Exception as e:
            logger.error(f"ANIMESAMA: Erreur titre film {anime_slug} #{episode_num}: {e}")
            return None

    async def fetch_complete_anime_data(self, anime_slug: str) -> Optional[Dict[str, Any]]:
        """Récupère données complètes d'un anime."""
        anime_data = await self.get_anime_details(anime_slug)
        if not anime_data:
            return None
        
        seasons = await self.get_seasons(anime_slug)
        anime_data["seasons"] = seasons
        
        return anime_data


async def get_or_fetch_anime_details(animesama_details: AnimeSamaDetails, anime_slug: str) -> Optional[Dict[str, Any]]:
    """Obtient les détails d'un anime depuis le cache ou par récupération."""
    cache_id = f"as:{anime_slug}"
    cached_anime = await get_metadata_from_cache(cache_id)

    if cached_anime:
        logger.log("DATABASE", f"Cache hit {cache_id}")
        return cached_anime

    lock_key = f"metadata_fetch_{anime_slug}"
    try:
        async with DistributedLock(lock_key):
            cached_anime = await get_metadata_from_cache(cache_id)
            if cached_anime:
                logger.log("DATABASE", f"Cache hit après acquisition du verrou {cache_id}")
                return cached_anime

            logger.log("DATABASE", f"Cache miss {cache_id} - Fetch avec verrou")
            anime_data = await animesama_details.fetch_complete_anime_data(anime_slug)
            if anime_data:
                await set_metadata_to_cache(cache_id, anime_data)
            return anime_data
            
    except LockAcquisitionError:
        logger.warning(f"DATABASE: Verrou impossible {anime_slug}, tentative sans verrou")
        anime_data = await animesama_details.fetch_complete_anime_data(anime_slug)
        if anime_data:
            await set_metadata_to_cache(cache_id, anime_data)
        return anime_data
    except Exception as e:
        logger.error(f"ANIMESAMA: Erreur inattendue détails {anime_slug}: {e}")
        return None