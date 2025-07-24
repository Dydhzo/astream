from typing import List, Optional, Dict, Any
import asyncio

from astream.utils.logger import logger
from astream.utils.dependencies import get_animesama_api, get_animesama_player
from astream.scrapers.animesama_details import get_or_fetch_anime_details
from astream.utils.animesama_utils import create_seasons_dict


class AnimeSamaService:
    """Service principal logique métier AnimeSama."""
    
    def __init__(self):
        pass
    
    async def get_catalog_data(self, search: Optional[str] = None, genre: Optional[str] = None, 
                              language: Optional[str] = None, client_ip: Optional[str] = None) -> List[Dict[str, Any]]:
        """Récupère données catalogue avec filtres optionnels."""
        try:
            animesama_api = await get_animesama_api()
            
            if client_ip:
                animesama_api.set_client_ip(client_ip)
            
            if search:
                logger.info(f"🐍 ANIMESAMA: Recherche '{search}' (genre: {genre}, langue: {language})")
                return await animesama_api.search_anime(search, language, genre)
            else:
                logger.info("🐍 ANIMESAMA: Récupération contenu homepage complet")
                return await animesama_api.get_homepage_content()
                
        except Exception as e:
            logger.error(f"🐍 ANIMESAMA: Erreur récupération catalogue: {e}")
            return []

    async def get_anime_metadata(self, anime_id: str, client_ip: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Récupère métadonnées complètes d'un anime."""
        try:
            if not anime_id.startswith('as:'):
                logger.error(f"❌ ERROR: ID anime invalide: {anime_id}")
                return None
            
            anime_slug = anime_id.replace('as:', '')
            logger.debug(f"🐍 ANIMESAMA: Récupération métadonnées pour {anime_slug}")
            
            animesama_api = await get_animesama_api()
            if client_ip:
                animesama_api.set_client_ip(client_ip)
            
            anime_data = await get_or_fetch_anime_details(animesama_api.details, anime_slug)
            
            if not anime_data:
                logger.warning(f"⚠️ WARNING: Aucune donnée trouvée pour {anime_slug}")
                return None
            
            return await self._enrich_metadata_with_episode_counts(anime_data, client_ip)
            
        except Exception as e:
            logger.error(f"🐍 ANIMESAMA: Erreur récupération métadonnées {anime_id}: {e}")
            return None

    async def get_episode_streams(self, episode_id: str, client_ip: Optional[str] = None) -> List[Dict[str, Any]]:
        """Récupère streams pour un épisode."""
        try:
            parsed_id = self._parse_media_id(episode_id)
            if not parsed_id:
                return []
            
            anime_slug = parsed_id['anime_slug']
            season_number = parsed_id['season_number']
            episode_number = parsed_id['episode_number']
            
            logger.debug(f"🎬 STREAM: Récupération streams {anime_slug} S{season_number}E{episode_number}")
            
            animesama_api = await get_animesama_api()
            if client_ip:
                animesama_api.set_client_ip(client_ip)
            
            return await animesama_api.get_episode_streams(anime_slug, season_number, episode_number)
            
        except Exception as e:
            logger.error(f"🎬 STREAM: Erreur récupération streams {episode_id}: {e}")
            return []

    async def get_film_title(self, anime_slug: str, episode_num: int, client_ip: Optional[str] = None) -> Optional[str]:
        """Récupère titre d'un film."""
        try:
            animesama_api = await get_animesama_api()
            if client_ip:
                animesama_api.set_client_ip(client_ip)
            
            return await animesama_api.get_film_title(anime_slug, episode_num)
            
        except Exception as e:
            logger.error(f"🐍 ANIMESAMA: Erreur récupération titre film {anime_slug}#{episode_num}: {e}")
            return None

    def extract_available_genres(self, catalog_data: List[Dict[str, Any]]) -> List[str]:
        """Extrait genres disponibles depuis données catalogue."""
        try:
            genres = set()
            
            for anime in catalog_data:
                anime_genres = anime.get('genres', '')
                if isinstance(anime_genres, str) and anime_genres:
                    genre_list = [g.strip() for g in anime_genres.split(',') if g.strip()]
                    genres.update(genre_list)
                elif isinstance(anime_genres, list):
                    genres.update(anime_genres)
            
            cleaned_genres = [g for g in genres if len(g) > 1 and g not in ['N/A', 'n/a', '']]
            return sorted(cleaned_genres)
            
        except Exception as e:
            logger.warning(f"⚠️ WARNING: Erreur extraction genres: {e}")
            return []

    def _parse_media_id(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Parse episode_id format as:anime_slug:s1e2."""
        try:
            import re
            
            pattern = r'^as:([^:]+):s(\d+)e(\d+)$'
            match = re.match(pattern, episode_id)
            
            if not match:
                logger.error(f"❌ ERROR: Format episode_id invalide: {episode_id}")
                return None
            
            return {
                'anime_slug': match.group(1),
                'season_number': int(match.group(2)),
                'episode_number': int(match.group(3))
            }
            
        except Exception as e:
            logger.error(f"❌ ERROR: Erreur parsing episode_id {episode_id}: {e}")
            return None

    async def _enrich_metadata_with_episode_counts(self, anime_data: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        """Enrichit métadonnées avec comptage épisodes parallele."""
        try:
            seasons = anime_data.get('seasons', [])
            if not seasons:
                return anime_data
            
            anime_slug = anime_data.get('slug')
            if not anime_slug:
                return anime_data
            
            animesama_player = await get_animesama_player()
            if client_ip:
                animesama_player.set_client_ip(client_ip)
            
            async def count_season_episodes(season_data):
                try:
                    episode_counts = await animesama_player.get_available_episodes_count(anime_slug, season_data)
                    season_data = season_data.copy()
                    season_data['episode_counts'] = episode_counts
                    season_data['total_episodes'] = max(episode_counts.values()) if episode_counts else 0
                    return season_data
                except Exception as e:
                    logger.warning(f"⚠️ WARNING: Erreur comptage épisodes saison {season_data.get('season_number')}: {e}")
                    season_data = season_data.copy()
                    season_data['episode_counts'] = {}
                    season_data['total_episodes'] = 0
                    return season_data
            
            enriched_seasons = await asyncio.gather(*[count_season_episodes(season) for season in seasons])
            
            enriched_anime_data = anime_data.copy()
            enriched_anime_data['seasons'] = enriched_seasons
            
            logger.debug(f"🔍 DEBUG: Métadonnées enrichies {anime_slug}: {len(enriched_seasons)} saisons")
            return enriched_anime_data
            
        except Exception as e:
            logger.warning(f"⚠️ WARNING: Erreur enrichissement métadonnées: {e}")
            return anime_data