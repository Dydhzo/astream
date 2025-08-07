from typing import Optional, Tuple, Dict, Any
import re

from astream.utils.logger import logger


class MediaIdParser:
    """Parser unifié pour les IDs de média."""
    
    @staticmethod
    def parse_episode_id(episode_id: str) -> Optional[Dict[str, Any]]:
        """Parse un episode_id au format as:anime_slug ou as:anime_slug:s1e1."""
        """Parse un episode_id au format as:anime_slug ou as:anime_slug:s1e1."""
        if "as:" not in episode_id:
            return None  # Format invalide
            
        try:
            parts = episode_id.split(":")  # Découper l'ID
            if len(parts) == 2:  # Format métadonnées seulement
                return {
                    'anime_slug': parts[1],
                    'season_number': None,
                    'episode_number': None,
                    'is_metadata_only': True
                }
            elif len(parts) == 3:
                anime_slug = parts[1]
                episode_info = parts[2]
                
                season_num, episode_num = MediaIdParser._extract_season_episode_numbers(episode_info)
                if season_num is None or episode_num is None:
                    return None
                    
                return {
                    'anime_slug': anime_slug,
                    'season_number': season_num,
                    'episode_number': episode_num,
                    'is_metadata_only': False,
                    'episode_info': episode_info
                }
            else:
                logger.error(f"Format episode_id invalide: '{episode_id}'")
                return None
        except (IndexError, ValueError) as e:
            logger.error(f"Erreur parsing episode_id '{episode_id}': {e}")
            return None
    
    @staticmethod
    def _extract_season_episode_numbers(episode_info: str) -> Tuple[Optional[int], Optional[int]]:
        """Extrait les numéros de saison et épisode depuis le format s{season}e{episode}."""
        try:
            match = re.match(r's(\d+)e(\d+)', episode_info)
            if match:
                return int(match.group(1)), int(match.group(2))
            return None, None
        except Exception as e:
            logger.error(f"Erreur extraction episode_info: {e}")
            return None, None
    
    @staticmethod
    def format_episode_id(anime_slug: str, season: int, episode: int) -> str:
        """Formate un episode_id."""
        return f"as:{anime_slug}:s{season}e{episode}"