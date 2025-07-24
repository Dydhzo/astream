from typing import List, Optional, Dict, Any

from astream.utils.http_client import HttpClient, BaseClient
from astream.utils.logger import logger
from astream.utils.animesama_utils import create_seasons_dict
from astream.scrapers.animesama_catalog import AnimeSamaCatalog
from astream.scrapers.animesama_details import AnimeSamaDetails, get_or_fetch_anime_details


class AnimeSamaAPI(BaseClient):
    """Client principal pour scraper anime-sama.fr."""
    
    def __init__(self, client: HttpClient):
        super().__init__()
        self.base_url = "https://anime-sama.fr"
        self.client = client
        self._current_client_ip = None
        
        self.catalog = AnimeSamaCatalog(client)
        self.details = AnimeSamaDetails(client)
    
    def set_client_ip(self, client_ip: str) -> None:
        """Définit l'IP du client pour le rate limiting."""
        self._current_client_ip = client_ip
        self.catalog.set_client_ip(client_ip)
        self.details.set_client_ip(client_ip)
    
    async def get_homepage_content(self) -> List[Dict[str, Any]]:
        """Récupère le contenu de la page d'accueil anime-sama."""
        return await self.catalog.get_homepage_content()

    async def search_anime(self, query: str, language: Optional[str] = None, genre: Optional[str] = None) -> List[Dict[str, Any]]:
        """Recherche des animes sur anime-sama."""
        return await self.catalog.search_anime(query, language, genre)

    async def get_anime_details(self, anime_slug: str) -> Optional[Dict[str, Any]]:
        """Récupère les détails d'un anime par son slug."""
        return await self.details.get_anime_details(anime_slug)

    async def get_seasons(self, anime_slug: str) -> List[Dict[str, Any]]:
        """Récupère les saisons disponibles pour un anime."""
        return await self.details.get_seasons(anime_slug)

    async def get_film_title(self, anime_slug: str, episode_num: int) -> Optional[str]:
        """Récupère le titre d'un film depuis anime-sama."""
        return await self.details.get_film_title(anime_slug, episode_num)

    async def get_episode_streams(self, anime_slug: str, season_number: int, episode_number: int, language_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Récupère les streams pour un épisode."""
        try:
            anime_data = await get_or_fetch_anime_details(self.details, anime_slug)
            if not anime_data:
                logger.error(f"🐍 ANIMESAMA: Impossible de récupérer les données pour {anime_slug}")
                return []
            
            seasons = anime_data.get("seasons", [])
            if not seasons:
                logger.warning(f"🐍 ANIMESAMA: Aucune saison trouvée pour {anime_slug}")
                return []
            
            seasons_dict = create_seasons_dict(seasons)
            
            season_data = seasons_dict.get(season_number)
            if not season_data:
                logger.warning(f"🐍 ANIMESAMA: Saison {season_number} non trouvée pour {anime_slug}")
                return []
            
            from astream.scrapers.animesama_player import AnimeSamaPlayer
            player = AnimeSamaPlayer(self.client)
            player.set_client_ip(self._current_client_ip)
            
            return await player.get_episode_streams(anime_slug, season_data, episode_number, language_filter)
            
        except Exception as e:
            logger.error(f"🐍 ANIMESAMA: Erreur récupération streams pour {anime_slug}: {e}")
            return []