import asyncio
from typing import List, Optional, Dict, Any

from astream.utils.logger import logger
from astream.utils.base_scraper import BaseScraper
from astream.utils.database import get_metadata_from_cache, set_metadata_to_cache
from astream.scrapers.animesama_player_extractor import AnimeSamaPlayerExtractor
from astream.scrapers.animesama_video_resolver import AnimeSamaVideoResolver
from astream.config.app_settings import settings
from astream.utils.stream_formatter import format_stream_for_stremio


class AnimeSamaPlayer(BaseScraper):
    """Lecteur intelligent d'épisodes anime-sama avec mappage automatique."""
    
    def __init__(self, client):
        super().__init__(client, settings.ANIMESAMA_URL)
        self.extractor = AnimeSamaPlayerExtractor(client)
        self.resolver = AnimeSamaVideoResolver(client)

    def set_client_ip(self, client_ip: str) -> None:
        """Définit l'IP client pour rate limiting."""
        super().set_client_ip(client_ip)
        self.extractor.set_client_ip(client_ip)
        self.resolver.set_client_ip(client_ip)

    async def get_episode_streams(self, anime_slug: str, season_data: Dict[str, Any], episode_number: int, language_filter: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Récupère les streams pour un épisode."""
        logger.log("STREAM", f"Génération streams temps réel {anime_slug} S{season_data.get('season_number')}E{episode_number}")
        
        try:
            logger.log("STREAM", f"Récupération streams {anime_slug} S{season_data.get('season_number')}E{episode_number}")
            
            player_urls_with_language = await self.extractor.extract_player_urls_smart_mapping_with_language(
                anime_slug, season_data, episode_number, language_filter, config
            )
            
            if not player_urls_with_language:
                logger.log("WARNING", f"STREAM: Aucun player trouvé {anime_slug} S{season_data.get('season_number')}E{episode_number}")
                return []
            
            video_urls_with_language = await self.resolver.extract_video_urls_from_players_with_language(
                player_urls_with_language
            )
            
            streams = []
            season_num = season_data.get('season_number')
            
            for video_data in video_urls_with_language:
                video_url = video_data["url"]
                detected_language = video_data["language"] or "VOSTFR"
                
                streams.append(
                    format_stream_for_stremio(video_url, detected_language, anime_slug, season_num)
                )
            
            
            logger.log("INFO", f"SUCCESS: Trouvé {len(streams)} streams {anime_slug} S{season_num}E{episode_number}")
            return streams
            
        except Exception as e:
            logger.log("ERROR", f"Erreur récupération streams: {e}")
            return []

    async def get_available_episodes_count(self, anime_slug: str, season_data: Dict[str, Any]) -> Dict[str, int]:
        """Compte les épisodes disponibles par langue."""
        try:
            logger.log("DEBUG", f"Comptage épisodes {anime_slug} S{season_data.get('season_number')}")
            
            languages_to_check = ["vostfr", "vf", "vf1", "vf2"]
            episode_counts = {}
            
            async def count_for_language_with_sub_seasons(language: str) -> tuple[str, int]:
                try:
                    season_path = season_data.get("path", "")
                    main_season_url = f"{self.base_url}/catalogue/{anime_slug}/{season_path}/{language.lower()}/"
                    
                    main_count = await self.extractor._get_episode_count_from_url(main_season_url)
                    logger.log("DEBUG", f"Saison principale {anime_slug} S{season_data.get('season_number')} ({language}): {main_count} épisodes")
                    
                    total_count = main_count
                    for sub_season in season_data.get("sub_seasons", []):
                        sub_path = sub_season.get("path", "")
                        if sub_path:
                            sub_url = f"{self.base_url}/catalogue/{anime_slug}/{sub_path}/{language.lower()}/"
                            try:
                                sub_count = await self.extractor._get_episode_count_from_url(sub_url)
                                if sub_count > 0:
                                    total_count += sub_count
                                    logger.log("DEBUG", f"Sous-saison {sub_path} ({language}): +{sub_count} épisodes")
                            except Exception as e:
                                logger.log("DEBUG", f"Erreur sous-saison {sub_path} ({language}): {e}")
                                continue
                    
                    logger.log("DEBUG", f"Total {anime_slug} S{season_data.get('season_number')} ({language}): {total_count} épisodes")
                    return language, total_count
                    
                except Exception as e:
                    logger.log("WARNING", f"Erreur comptage langue {language}: {e}")
                    return language, 0
            
            tasks = [count_for_language_with_sub_seasons(lang) for lang in languages_to_check]
            results = await asyncio.gather(*tasks)
            
            for language, count in results:
                episode_counts[language] = count
            
            total_episodes = max(episode_counts.values()) if episode_counts else 0
            logger.log("DEBUG", f"{anime_slug} S{season_data.get('season_number')}: {total_episodes} épisodes TOTAL")
            
            return episode_counts
            
        except Exception as e:
            logger.log("ERROR", f"Erreur comptage épisodes: {e}")
            return {}

    def map_episode_to_season(self, episode_number: int, season_data: Dict[str, Any], episode_counts: Dict[str, int]) -> Dict[str, Any]:
        """Mappe un épisode vers la bonne saison/sous-saison."""
        try:
            main_season_count = max(episode_counts.values()) if episode_counts else 0
            sub_seasons = season_data.get("sub_seasons", [])
            
            # Cas 1: Pas de sous-saisons ou épisode dans saison principale
            if not sub_seasons or episode_number <= main_season_count:
                return {
                    "season_path": season_data.get("path", ""),
                    "target_episode": episode_number,
                    "is_sub_season": False,
                    "sub_season_info": None
                }
            
            # Cas 2: L'épisode est dans une sous-saison
            relative_episode = episode_number - main_season_count
            
            # Mapper vers la première sous-saison disponible
            if sub_seasons:
                sub_season = sub_seasons[0]
                return {
                    "season_path": sub_season.get("path", ""),
                    "target_episode": relative_episode,
                    "is_sub_season": True,
                    "sub_season_info": sub_season
                }
            
            # Cas 3: Fallback vers saison principale
            return {
                "season_path": season_data.get("path", ""),
                "target_episode": episode_number,
                "is_sub_season": False,
                "sub_season_info": None
            }
            
        except Exception as e:
            logger.log("WARNING", f"Erreur mapping épisode {episode_number}: {e}")
            return {
                "season_path": season_data.get("path", ""),
                "target_episode": episode_number,
                "is_sub_season": False,
                "sub_season_info": None
            }