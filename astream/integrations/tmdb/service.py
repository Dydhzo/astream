import asyncio
from typing import Optional, Dict, List, Any, Tuple
from urllib.parse import unquote

from astream.integrations.tmdb.client import TMDBClient
from astream.utils.http.client import HttpClient
from astream.utils.logger import logger
from astream.utils.validation.models import ConfigModel
from astream.config.settings import settings


class TMDBService:
    """Service pour intégrer TMDB avec Anime-Sama."""
    
    def __init__(self, http_client: HttpClient):
        self.http_client = http_client
    
    def _get_tmdb_client(self, config: ConfigModel) -> Optional[TMDBClient]:
        """Crée client TMDB avec clé API (utilisateur prioritaire)."""
        api_key = config.tmdbApiKey if config.tmdbApiKey else settings.TMDB_API_KEY
        if not api_key:
            return None
        
        return TMDBClient(self.http_client, api_key)
    
    async def enhance_anime_metadata(self, anime_data: Dict[str, Any], config: ConfigModel) -> Dict[str, Any]:
        """Enrichit les métadonnées anime avec TMDB si activé."""
        if not config.tmdbEnabled:
            return anime_data
            
        tmdb_client = self._get_tmdb_client(config)
        if not tmdb_client:
            logger.log("TMDB", "Aucune clé API TMDB disponible")
            return anime_data
            
        try:
            title = anime_data.get("title", anime_data.get("name", ""))
            if not title:
                return anime_data
                
            clean_title = self._clean_title_for_search(title)
            logger.log("TMDB", f"Recherche TMDB pour: '{title}' -> '{clean_title}'")
            tmdb_anime = await tmdb_client.search_anime(clean_title)
            if not tmdb_anime:
                logger.log("TMDB", f"Aucun résultat TMDB pour: {title}")
                return anime_data
            
            logger.log("TMDB", f"Match TMDB trouvé: {tmdb_anime.get('name')} (ID: {tmdb_anime.get('id')})")
                
            media_type = tmdb_anime.get("media_type", "tv")
            tmdb_details = await tmdb_client.get_anime_details(tmdb_anime["id"], media_type)
            if not tmdb_details:
                return anime_data
            
            enhanced_data = anime_data.copy()
            
            if tmdb_details.get("images", {}).get("posters"):
                posters = tmdb_details["images"]["posters"]
                logger.debug(f"POSTERS TMDB: {len(posters)} disponibles pour {title}")
                
                selected_poster = None
                
                fr_posters = [poster for poster in posters if poster.get("iso_639_1") == "fr"]
                if fr_posters:
                    selected_poster = max(fr_posters, key=lambda x: x.get("width", 0) * x.get("height", 0))
                    logger.debug(f"Poster FR sélectionné: {selected_poster.get('width')}x{selected_poster.get('height')}")
                
                elif any(poster.get("iso_639_1") == "en" for poster in posters):
                    en_posters = [poster for poster in posters if poster.get("iso_639_1") == "en"]
                    selected_poster = max(en_posters, key=lambda x: x.get("width", 0) * x.get("height", 0))
                    logger.debug(f"Poster EN sélectionné: {selected_poster.get('width')}x{selected_poster.get('height')}")
                
                else:
                    selected_poster = max(posters, key=lambda x: x.get("width", 0) * x.get("height", 0))
                    lang = selected_poster.get("iso_639_1", "null")
                    logger.debug(f"Poster {lang} sélectionné: {selected_poster.get('width')}x{selected_poster.get('height')}")
                
                if selected_poster:
                    enhanced_data["poster"] = tmdb_client.get_poster_url(selected_poster["file_path"])
                    enhanced_data["image"] = enhanced_data["poster"]
                    logger.debug(f"Poster appliqué: {title}")
            
            elif tmdb_details.get("poster_path"):
                enhanced_data["poster"] = tmdb_client.get_poster_url(tmdb_details["poster_path"])
                enhanced_data["image"] = enhanced_data["poster"]
                logger.log("TMDB", f"Poster par défaut ajouté pour: {title}")
                
            if tmdb_details.get("images", {}).get("backdrops"):
                backdrops = tmdb_details["images"]["backdrops"]
                logger.debug(f"BACKGROUNDS TMDB: {len(backdrops)} disponibles pour {title}")
                
                no_lang_backdrops = [bg for bg in backdrops if bg.get("iso_639_1") is None]
                
                if no_lang_backdrops:
                    selected_background = max(no_lang_backdrops, key=lambda x: x.get("width", 0) * x.get("height", 0))
                    enhanced_data["background"] = tmdb_client.get_backdrop_url(selected_background["file_path"])
                    logger.log("TMDB", f"Background SANS LANGUE HAUTE RES: {selected_background.get('width')}x{selected_background.get('height')}")
                else:
                    logger.log("TMDB", f"Aucun background sans langue pour: {title}")
            
            elif tmdb_details.get("backdrop_path"):
                enhanced_data["background"] = tmdb_client.get_backdrop_url(tmdb_details["backdrop_path"])
                logger.log("TMDB", f"Background par défaut ajouté pour: {title}")
                
            if tmdb_details.get("images", {}).get("logos"):
                logos = tmdb_details["images"]["logos"]
                logger.log("TMDB", f"LOGOS TMDB trouvés pour {title}: {len(logos)} logos")
                
                for i, logo in enumerate(logos):
                    lang = logo.get("iso_639_1", "null")
                    width = logo.get("width", 0)
                    height = logo.get("height", 0)
                    file_path = logo.get("file_path", "")
                    logger.log("TMDB", f"  Logo {i+1}: langue={lang}, résolution={width}x{height}, path={file_path}")
                
                selected_logo = None
                
                fr_logos = [logo for logo in logos if logo.get("iso_639_1") == "fr"]
                if fr_logos:
                    selected_logo = max(fr_logos, key=lambda x: x.get("width", 0) * x.get("height", 0))
                    logger.log("TMDB", f"Logo français HAUTE RES sélectionné: {selected_logo.get('width')}x{selected_logo.get('height')}")
                
                elif any(logo.get("iso_639_1") == "en" for logo in logos):
                    en_logos = [logo for logo in logos if logo.get("iso_639_1") == "en"]
                    selected_logo = max(en_logos, key=lambda x: x.get("width", 0) * x.get("height", 0))
                    logger.log("TMDB", f"Logo anglais HAUTE RES sélectionné: {selected_logo.get('width')}x{selected_logo.get('height')}")
                
                else:
                    selected_logo = max(logos, key=lambda x: x.get("width", 0) * x.get("height", 0))
                    lang = selected_logo.get("iso_639_1", "null")
                    logger.log("TMDB", f"Logo {lang} HAUTE RES sélectionné: {selected_logo.get('width')}x{selected_logo.get('height')}")
                
                if selected_logo:
                    logo_url = tmdb_client.get_logo_url(selected_logo["file_path"])
                    enhanced_data["logo"] = logo_url
                    logger.log("TMDB", f"Logo final pour {title}: {logo_url}")
            else:
                logger.log("TMDB", f"Aucun logo TMDB pour: {title}")
                    
            # Description (PRIORITÉ TMDB français)
            tmdb_description = tmdb_details.get("overview", "").strip()
            if tmdb_description and len(tmdb_description) > 10:  # Vérifier qualité
                enhanced_data["description"] = tmdb_description
                enhanced_data["synopsis"] = tmdb_description  # Compatibilité
                logger.log("TMDB", f"Description française ajoutée pour: {title}")
            else:
                logger.log("TMDB", f"Description TMDB manquante/courte pour: {title} - conserve Anime-Sama")
                
            # Trailer YouTube (format Stremio)
            if tmdb_details.get("videos"):
                trailer_id = tmdb_client.extract_trailer_id(tmdb_details["videos"])
                if trailer_id:
                    enhanced_data["trailers"] = [{"source": trailer_id, "type": "Trailer"}]  # Format Stremio
                    logger.log("TMDB", f"Trailer YouTube ajouté pour {title}: {trailer_id}")
                else:
                    logger.log("TMDB", f"Aucun trailer YouTube trouvé pour: {title}")
                    
            # ANNÉES début-fin (système intelligent)
            start_year = None
            end_year = None
            
            if tmdb_details.get("first_air_date"):
                start_year = tmdb_details["first_air_date"][:4]
            
            # SEULEMENT si vraiment terminé ET avec date de fin
            if tmdb_details.get("last_air_date") and tmdb_details.get("status") == "Ended":
                end_year = tmdb_details["last_air_date"][:4]
            # PAS d'année de fin si pas terminé ou pas de date de fin
            
            # Construire l'affichage des années
            if start_year and end_year:
                if start_year == end_year:
                    enhanced_data["year_range"] = start_year  # "2024"
                else:
                    enhanced_data["year_range"] = f"{start_year}-{end_year}"  # "1999-2010"
            elif start_year:
                if tmdb_details.get("status") in ["Returning Series", "In Production"]:
                    enhanced_data["year_range"] = f"{start_year}-"  # "1999-" (en cours)
                else:
                    enhanced_data["year_range"] = start_year  # "2024" (pas d'info fin)
            
            # Compatibilité
            if enhanced_data.get("year_range"):
                enhanced_data["year"] = enhanced_data["year_range"]
                logger.log("TMDB", f"Années définies: {enhanced_data['year_range']} pour {title}")
            
            # NOTE TMDB + IMDB ID pour lien cliquable
            imdb_id = None
            tmdb_rating = None
            
            # Récupérer l'IMDB ID depuis external_ids
            if tmdb_details.get("external_ids", {}).get("imdb_id"):
                imdb_id = tmdb_details["external_ids"]["imdb_id"]
                logger.log("TMDB", f"IMDB ID trouvé: {imdb_id} pour {title}")
            
            # Récupérer la note TMDB
            if tmdb_details.get("vote_average") and tmdb_details["vote_average"] > 0:
                tmdb_rating = round(tmdb_details["vote_average"], 1)
                enhanced_data["imdbRating"] = str(tmdb_rating)  # Affichage dans Stremio
                logger.log("TMDB", f"Note TMDB: {tmdb_rating} pour {title}")
            
            # Stocker les données pour les liens
            if imdb_id:
                enhanced_data["imdb_id"] = imdb_id
            if tmdb_rating:
                enhanced_data["tmdb_rating"] = tmdb_rating
            
            # DATE DE SORTIE - Films vs Séries
            if media_type == "movie" and tmdb_details.get("release_date"):
                enhanced_data["year"] = tmdb_details["release_date"][:4]  # Année seulement
                logger.log("TMDB", f"Date sortie film: {tmdb_details['release_date']} pour {title}")
            elif media_type == "tv" and tmdb_details.get("first_air_date"):
                enhanced_data["year"] = tmdb_details["first_air_date"][:4]  # Année seulement
                logger.log("TMDB", f"Date première diffusion: {tmdb_details['first_air_date']} pour {title}")
                
            # DURÉE - Films vs Séries
            if media_type == "movie" and tmdb_details.get("runtime"):
                runtime = tmdb_details["runtime"]
                enhanced_data["runtime"] = f"{runtime} min"
                logger.log("TMDB", f"Durée film: {runtime} min pour {title}")
            elif media_type == "tv":
                # Stratégie 1: Durée officielle de la série
                if tmdb_details.get("episode_run_time") and tmdb_details["episode_run_time"]:
                    episode_duration = tmdb_details["episode_run_time"][0]  # Premier élément = durée typique
                    enhanced_data["runtime"] = f"{episode_duration} min"
                    logger.log("TMDB", f"Durée épisode officielle: {episode_duration} min pour {title}")
                
                # Stratégie 2: Fallback sur la durée du S1E1
                else:
                    logger.log("TMDB", f"Pas de episode_run_time pour {title}, tentative fallback S1E1...")
                    try:
                        # Récupérer les détails de la saison 1
                        tmdb_id = tmdb_details.get("id")
                        season_url = f"{tmdb_client.base_url}/tv/{tmdb_id}/season/1"
                        season_params = {
                            "api_key": tmdb_client.api_key,
                            "language": "fr-FR"
                        }
                        season_response = await tmdb_client.client.get(season_url, params=season_params)
                        season_data = season_response.json()
                        
                        # Chercher la durée du premier épisode
                        if season_data and "episodes" in season_data and season_data["episodes"]:
                            first_episode = season_data["episodes"][0]
                            if first_episode.get("runtime"):
                                runtime = first_episode["runtime"]
                                enhanced_data["runtime"] = f"{runtime} min"
                                logger.log("TMDB", f"Durée S1E1 utilisée: {runtime} min pour {title}")
                            else:
                                logger.log("TMDB", f"Aucune durée pour S1E1 de: {title}")
                        else:
                            logger.log("TMDB", f"Pas d'épisodes trouvés pour S1 de: {title}")
                            
                    except Exception as e:
                        logger.warning(f"Erreur récupération durée S1E1 pour {title}: {e}")
            else:
                logger.log("TMDB", f"Type média non géré pour durée: {media_type}")
                
                
            # IMPORTANT: Conserver les genres d'Anime-Sama
            # enhanced_data["genres"] reste inchangé
            
            logger.log("TMDB", f"Métadonnées enrichies pour: {title}")
            return enhanced_data
            
        except Exception as e:
            logger.error(f"Erreur enrichissement TMDB pour '{title}': {e}")
            return anime_data
    
    async def enhance_episodes_metadata(self, anime_data: Dict[str, Any], config: ConfigModel) -> Dict[str, Any]:
        """Enrichit les métadonnées des épisodes avec TMDB."""
        if not config.tmdbEnabled:
            return anime_data
            
        tmdb_client = self._get_tmdb_client(config)
        if not tmdb_client:
            return anime_data
            
        try:
            title = anime_data.get("title", anime_data.get("name", ""))
            clean_title = self._clean_title_for_search(title)
            
            # Rechercher l'anime sur TMDB
            tmdb_anime = await tmdb_client.search_anime(clean_title)
            if not tmdb_anime:
                return anime_data
                
            # Récupérer les détails des saisons
            tmdb_details = await tmdb_client.get_anime_details(tmdb_anime["id"])
            if not tmdb_details or not tmdb_details.get("seasons"):
                return anime_data
                
            enhanced_data = anime_data.copy()
            
            # Traiter chaque saison
            if "videos" in enhanced_data:
                enhanced_videos = []
                
                # Créer un mapping TMDB des épisodes
                tmdb_episodes_map = await self._create_tmdb_episodes_map(
                    tmdb_client, tmdb_anime["id"], tmdb_details["seasons"]
                )
                
                for video in enhanced_data["videos"]:
                    enhanced_video = video.copy()
                    
                    # Parser l'ID de l'épisode (as:slug:s1e1)
                    episode_info = self._parse_episode_id(video.get("id", ""))
                    if episode_info:
                        season_num, episode_num = episode_info["season"], episode_info["episode"]
                        
                        # Chercher l'épisode correspondant dans TMDB
                        tmdb_episode = tmdb_episodes_map.get(f"s{season_num}e{episode_num}")
                        if tmdb_episode:
                            # METADATA ÉPISODES - SEULEMENT SI MAPPING INTELLIGENT ACTIVÉ
                            if config.tmdbEpisodeMapping and season_num > 0:
                                # IMAGES D'ÉPISODES
                                if tmdb_episode.get("still_path"):
                                    enhanced_video["thumbnail"] = tmdb_client.get_episode_image_url(
                                        tmdb_episode["still_path"]
                                    )
                                    logger.log("TMDB", f"Image épisode TMDB: S{season_num}E{episode_num}")
                                
                                # DATE DE SORTIE ÉPISODE
                                if tmdb_episode.get("air_date"):
                                    # Format: "2024-01-15" -> "2024-01-15T00:00:00.000Z"
                                    air_date = tmdb_episode["air_date"]
                                    enhanced_video["released"] = f"{air_date}T00:00:00.000Z"
                                    logger.log("TMDB", f"Date sortie épisode: S{season_num}E{episode_num} - {air_date}")
                                
                                # TITRES D'ÉPISODES
                                if tmdb_episode.get("name"):
                                    enhanced_video["title"] = tmdb_episode["name"]
                                    logger.log("TMDB", f"Titre épisode TMDB: S{season_num}E{episode_num} - {tmdb_episode['name']}")
                                    
                                # DESCRIPTIONS D'ÉPISODES
                                if tmdb_episode.get("overview") and len(tmdb_episode["overview"].strip()) > 10:
                                    enhanced_video["overview"] = tmdb_episode["overview"]
                                    logger.log("TMDB", f"Description épisode TMDB: S{season_num}E{episode_num}")
                            else:
                                if season_num > 0:
                                    logger.log("TMDB", f"Mapping épisodes désactivé - données Anime-Sama conservées pour S{season_num}E{episode_num}")
                    
                    enhanced_videos.append(enhanced_video)
                
                enhanced_data["videos"] = enhanced_videos
                
            logger.log("TMDB", f"Épisodes enrichis avec TMDB pour: {title} ({len(enhanced_videos)} épisodes)")
            return enhanced_data
            
        except Exception as e:
            logger.error(f"Erreur enrichissement épisodes TMDB: {e}")
            return anime_data
    
    async def _create_tmdb_episodes_map(self, tmdb_client: TMDBClient, tmdb_id: int, seasons: List[Dict]) -> Dict[str, Dict]:
        """Crée un mapping des épisodes TMDB par saison."""
        episodes_map = {}
        
        # Traiter uniquement les saisons normales (pas les spéciaux)
        normal_seasons = [s for s in seasons if s.get("season_number", 0) > 0]
        
        # Récupérer les détails de toutes les saisons en parallèle
        season_tasks = [
            tmdb_client.get_season_details(tmdb_id, season["season_number"])
            for season in normal_seasons
        ]
        
        season_results = await asyncio.gather(*season_tasks, return_exceptions=True)
        
        for i, season_data in enumerate(season_results):
            if isinstance(season_data, Exception) or not season_data:
                continue
                
            season_number = normal_seasons[i]["season_number"]
            
            if "episodes" in season_data:
                for episode in season_data["episodes"]:
                    episode_number = episode.get("episode_number")
                    if episode_number:
                        # Clé format: s1e1, s2e5, etc.
                        key = f"s{season_number}e{episode_number}"
                        episodes_map[key] = episode
                        
        return episodes_map
    
    async def get_episodes_mapping(self, anime_data: Dict[str, Any], config: ConfigModel) -> Dict[str, Dict]:
        """Récupère seulement le mapping des épisodes TMDB sans modifier les données anime."""
        if not config.tmdbEnabled:
            return {}
            
        tmdb_client = self._get_tmdb_client(config)
        if not tmdb_client:
            return {}
            
        try:
            title = anime_data.get("title", anime_data.get("name", ""))
            clean_title = self._clean_title_for_search(title)
            
            # Rechercher l'anime sur TMDB
            tmdb_anime = await tmdb_client.search_anime(clean_title)
            if not tmdb_anime:
                return {}
                
            # Récupérer les détails des saisons
            tmdb_details = await tmdb_client.get_anime_details(tmdb_anime["id"])
            if not tmdb_details or not tmdb_details.get("seasons"):
                return {}
                
            # Créer le mapping des épisodes
            episodes_map = await self._create_tmdb_episodes_map(
                tmdb_client, tmdb_anime["id"], tmdb_details["seasons"]
            )
            
            logger.log("TMDB", f"Mapping épisodes créé: {len(episodes_map)} épisodes pour {title}")
            return episodes_map
            
        except Exception as e:
            logger.error(f"Erreur création mapping épisodes TMDB: {e}")
            return {}
    
    def _clean_title_for_search(self, title: str) -> str:
        """Nettoie un titre d'anime pour la recherche TMDB - CONSERVE LES DIFFÉRENCES IMPORTANTES."""
        if not title:
            return ""
            
        original_title = title
        title = title.strip()
        
        # PRÉSERVER les différences importantes (Naruto vs Naruto Shippuden)
        # Ne pas enlever "Shippuden", "Kai", "Brotherhood", etc.
        important_suffixes = [
            "shippuden", "kai", "brotherhood", "ultimate", "super", "gt", "z"
        ]
        
        has_important_suffix = any(suffix in title.lower() for suffix in important_suffixes)
        
        # Nettoyages légers SEULEMENT
        if not has_important_suffix:
            # Enlever les mentions de saison/épisode SEULEMENT si pas de suffixe important
            title = title.split(" - ")[0]  # "Title - Season 1" -> "Title"
            title = title.split(" (")[0]   # "Title (2023)" -> "Title"
            title = title.split(" saison")[0]  # "Title saison 2" -> "Title"
        
        # Nettoyages spécifiques pour anime (CONSERVATEURS)
        minimal_cleanups = {
            "  ": " ",  # Double espaces
            " OAV": "",
            " OVA": "",
            " Movie": "",
            " Film": "",
        }
        
        for old, new in minimal_cleanups.items():
            title = title.replace(old, new)
        
        # Normalisation des caractères MINIMALE
        char_replacements = {
            "é": "e", "è": "e", "ê": "e",
            "à": "a", "â": "a", 
            "ù": "u", "û": "u",
            "ô": "o", "ç": "c"
        }
        
        for old, new in char_replacements.items():
            title = title.replace(old, new)
            
        title = title.strip()
        
        if title != original_title:
            logger.log("TMDB", f"Titre '{original_title}' -> '{title}' (nettoyage conservateur)")
        else:
            logger.log("TMDB", f"Titre conservé intact: '{title}'")
            
        return title
    
    def _parse_episode_id(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Parse un ID d'épisode format as:slug:s1e1."""
        if not episode_id or not episode_id.startswith("as:"):
            return None
            
        parts = episode_id.split(":")
        if len(parts) < 3:
            return None
            
        # Dernier part contient s1e1
        season_episode = parts[-1]
        
        # Parser s1e1
        import re
        match = re.match(r's(\d+)e(\d+)', season_episode)
        if not match:
            return None
            
        return {
            "slug": parts[1],
            "season": int(match.group(1)),
            "episode": int(match.group(2))
        }