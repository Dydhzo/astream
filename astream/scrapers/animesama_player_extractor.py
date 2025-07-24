import re
import asyncio
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin

from astream.utils.logger import logger
from astream.utils.base_scraper import BaseScraper
from astream.utils.database import get_metadata_from_cache, set_metadata_to_cache
from astream.config.app_settings import settings
from astream.utils.animesama_utils import extract_episodes_from_js


class AnimeSamaPlayerExtractor(BaseScraper):
    """Extracteur d'URLs de players."""
    
    def __init__(self, client):
        super().__init__(client, "https://anime-sama.fr")

    async def extract_player_urls_smart_mapping_with_language(self, anime_slug: str, season_data: Dict[str, Any], episode_number: int, language_filter: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Extrait les URLs de players avec mapping intelligent."""
        season_num = season_data.get('season_number')
        cache_key = f"as:{anime_slug}:s{season_num}e{episode_number}:players"
        
        cached_players = await get_metadata_from_cache(cache_key)
        if cached_players:
            logger.info(f"🔒 DATABASE: Cache hit {cache_key} - Players récupérés")
            player_urls = cached_players.get("player_urls", [])
            
            # Filtrer selon language_filter puis réorganiser si nécessaire
            filtered_urls = self._filter_by_language(player_urls, language_filter)
            
            if (not language_filter or language_filter == "Tout") and config and "languageOrder" in config:
                user_language_order = config["languageOrder"]
                if user_language_order != "VOSTFR,VF":
                    filtered_urls = self._reorder_by_user_preference(filtered_urls, user_language_order)
            
            return filtered_urls
        
        logger.info(f"🔒 DATABASE: Cache miss {cache_key} - Extraction players")
        
        try:
            logger.debug(f"🔍 DEBUG: Mapping intelligent épisode {episode_number} {anime_slug} S{season_data.get('season_number')}")
            
            available_languages = season_data.get("languages", ["vostfr"])
            
            # Stocker l'ordre utilisateur pour réorganisation finale
            user_language_order = "VOSTFR,VF"
            if config and "languageOrder" in config:
                user_language_order = config["languageOrder"]
            
            # TOUJOURS extraire toutes les langues pour le cache unique
            languages_to_check = ["vostfr", "vf", "vf1", "vf2"]
            
            
            player_urls_with_language = []
            
            for language in languages_to_check:
                try:
                    urls = await self._extract_from_single_season(anime_slug, season_data, episode_number, language)
                    
                    for url in urls:
                        player_urls_with_language.append({
                            "url": url,
                            "language": language
                        })
                        
                except Exception as e:
                    logger.warning(f"⚠️ WARNING: Erreur extraction langue {language}: {e}")
                    continue
            
            # Stocker en cache dans l'ordre STANDARD (pas réorganisé)
            cache_data = {
                "player_urls": player_urls_with_language,
                "anime_slug": anime_slug,
                "season": season_num,
                "episode": episode_number,
                "language_filter": language_filter,
                "total_players": len(player_urls_with_language)
            }
            await set_metadata_to_cache(cache_key, cache_data, ttl=settings.EPISODE_PLAYERS_TTL)
            logger.info(f"🔒 DATABASE: Cache set {cache_key} - {len(player_urls_with_language)} players")
            
            # Filtrer selon language_filter puis réorganiser si nécessaire
            filtered_urls = self._filter_by_language(player_urls_with_language, language_filter)
            
            if (not language_filter or language_filter == "Tout") and user_language_order != "VOSTFR,VF":
                filtered_urls = self._reorder_by_user_preference(filtered_urls, user_language_order)
            
            return filtered_urls
            
        except Exception as e:
            logger.error(f"❌ ERROR: Erreur mapping intelligent: {e}")
            return []

    def _filter_by_language(self, player_urls_with_language, language_filter):
        """Filtre les player URLs selon le language_filter demandé."""
        if not language_filter or language_filter == "Tout":
            return player_urls_with_language
        
        if language_filter == "VOSTFR":
            allowed_langs = ["vostfr"]
        elif language_filter == "VF":
            allowed_langs = ["vf", "vf1", "vf2"]
        else:
            allowed_langs = [language_filter.lower()]
        
        return [player for player in player_urls_with_language 
                if player["language"] in allowed_langs]

    def _reorder_by_user_preference(self, player_urls_with_language, user_language_order):
        """Réorganise les player URLs selon l'ordre de préférence utilisateur."""
        user_order_list = [lang.strip().upper() for lang in user_language_order.split(",")]
        
        # Créer des groupes par langue
        language_groups = {}
        for player in player_urls_with_language:
            lang = player["language"]
            
            # Mapper les langues techniques vers les langues utilisateur
            if lang == "vostfr":
                user_lang = "VOSTFR"
            elif lang in ["vf", "vf1", "vf2"]:
                user_lang = "VF"
            else:
                user_lang = lang.upper()
            
            if user_lang not in language_groups:
                language_groups[user_lang] = []
            language_groups[user_lang].append(player)
        
        # Réorganiser selon l'ordre utilisateur
        reordered_players = []
        for user_lang in user_order_list:
            if user_lang in language_groups:
                reordered_players.extend(language_groups[user_lang])
        
        # Ajouter les langues non spécifiées à la fin
        for lang, players in language_groups.items():
            if lang not in user_order_list:
                reordered_players.extend(players)
        
        return reordered_players

    async def _extract_from_single_season(self, anime_slug: str, season_data: Dict[str, Any], episode_number: int, language: str) -> List[str]:
        """Extrait les URLs de players pour un épisode depuis une saison et langue données avec mapping intelligent."""
        try:
            
            season_path = season_data.get("path", "")
            main_url = f"{self.base_url}/catalogue/{anime_slug}/{season_path}/{language}/"
            
            main_season_episode_count = await self._get_episode_count_from_url(main_url)
            
            target_url = None
            target_episode_number = episode_number
            
            if episode_number <= main_season_episode_count:
                target_url = main_url
                target_episode_number = episode_number
            else:
                remaining_episodes = episode_number - main_season_episode_count
                
                for sub_season in season_data.get("sub_seasons", []):
                    sub_path = sub_season.get("path", "")
                    if not sub_path:
                        continue
                    
                    sub_url = f"{self.base_url}/catalogue/{anime_slug}/{sub_path}/{language}/"
                    sub_episode_count = await self._get_episode_count_from_url(sub_url)
                    
                    if remaining_episodes <= sub_episode_count:
                        target_url = sub_url
                        target_episode_number = remaining_episodes
                        break
                    else:
                        remaining_episodes -= sub_episode_count
                
                if not target_url:
                    logger.warning(f"⚠️ WARNING: Impossible de mapper épisode {episode_number} en {language}")
                    return []
            
            
            response = await self._rate_limited_request('get', target_url)
            response.raise_for_status()
            html = response.text
            
            episode_urls = await self._extract_from_episodes_js(target_url, html, target_episode_number)
            
            episode_urls = self._filter_excluded_domains(episode_urls)
            
            return episode_urls
            
        except Exception as e:
            logger.error(f"❌ ERROR: Erreur extraction: {e}")
            return []

    async def _extract_from_episodes_js(self, season_url: str, html: str, episode_number: int) -> List[str]:
        """Extrait les URLs d'épisode depuis le fichier episodes.js."""
        try:
            player_urls = []
            
            episodes_js_match = re.search(r'episodes\.js\?filever=\d+', html)
            
            if not episodes_js_match:
                return []
            
            episodes_js_filename = episodes_js_match.group(0)
            season_base_url = season_url.rstrip('/') + '/'
            episodes_js_url = season_base_url + episodes_js_filename
            
            
            response = await self._rate_limited_request('get', episodes_js_url)
            response.raise_for_status()
            js_content = response.text
            
            
            all_eps_matches = re.findall(r'var\s+eps\w*\s*=\s*\[[^\]]+\]', js_content)
            
            if not all_eps_matches:
                logger.warning(f"⚠️ WARNING: Aucun array eps dans episodes.js")
                return []
            
            
            for eps_match in all_eps_matches:
                eps_name_match = re.search(r'eps(\w*)', eps_match)
                if not eps_name_match:
                    continue
                
                eps_name = f"eps{eps_name_match.group(1)}"
                
                url_matches = re.findall(r"['\"]([^'\"]+)['\"]", eps_match)
                
                if len(url_matches) >= episode_number and url_matches[episode_number - 1]:
                    episode_url = url_matches[episode_number - 1]
                    
                    if episode_url and episode_url.strip() and self._is_video_player_url(episode_url):
                        if not episode_url.startswith('http'):
                            episode_url = urljoin(season_base_url, episode_url)
                        
                        player_urls.append(episode_url)
            
            return player_urls
            
        except Exception as e:
            logger.error(f"❌ ERROR: Erreur extraction episodes.js: {e}")
            return []

    async def _get_episode_count_from_url(self, season_url: str) -> int:
        """Détermine le nombre d'épisodes disponibles dans une saison."""
        try:
            response = await self._internal_request('get', season_url)
            response.raise_for_status()
            html = response.text
            
            episodes_js_match = re.search(r'episodes\.js\?filever=\d+', html)
            
            if not episodes_js_match:
                return 0
            
            episodes_js_filename = episodes_js_match.group(0)
            season_base_url = season_url.rstrip('/') + '/'
            episodes_js_url = season_base_url + episodes_js_filename
            
            response = await self._internal_request('get', episodes_js_url)
            response.raise_for_status()
            js_content = response.text
            
            all_eps_matches = re.findall(r'var\s+eps\w*\s*=\s*\[[^\]]+\]', js_content)
            max_episodes = 0
            
            for eps_match in all_eps_matches:
                url_matches = re.findall(r"['\"]([^'\"]+)['\"]", eps_match)
                valid_urls = [url for url in url_matches if self._is_video_player_url(url)]
                
                if len(valid_urls) > max_episodes:
                    max_episodes = len(valid_urls)
            
            episode_count = max_episodes
            
            return episode_count
            
        except Exception as e:
            return 0

    def _filter_excluded_domains(self, urls: List[str]) -> List[str]:
        """Filtre les URLs selon EXCLUDED_DOMAIN."""
        from astream.utils.domain_filters import filter_excluded_domains
        return filter_excluded_domains(urls)
    
    def _is_video_player_url(self, url: str) -> bool:
        """Vérifie si une URL est un player vidéo valide."""
        if not url or not url.strip():
            return False
            
        if not url.startswith('http'):
            return False
        
        excluded_extensions = ['.js', '.css', '.png', '.jpg', '.svg', '.woff', '.ico', '.gif', '.jpeg']
        url_lower = url.lower()
        
        for ext in excluded_extensions:
            if ext in url_lower:
                return False
        
        excluded_patterns = [
            '/assets/',
            '/templates/',
            '/static/',
            'anime-sama.fr/catalogue/',
            '#'
        ]
        
        for pattern in excluded_patterns:
            if pattern in url:
                return False
        
        return True