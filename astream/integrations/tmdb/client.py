import asyncio
import json
import re
import unicodedata
from typing import Optional, Dict, List, Any
from urllib.parse import quote
from difflib import SequenceMatcher

from astream.utils.http.client import HttpClient
from astream.utils.data.database import get_metadata_from_cache, set_metadata_to_cache
from astream.utils.logger import logger
from astream.config.settings import settings


def normalize_title(title: str) -> str:
    """Normalise un titre pour la comparaison intelligente."""
    if not title:
        return ""
    
    title = title.lower()
    title = unicodedata.normalize('NFD', title)
    title = ''.join(char for char in title if unicodedata.category(char) != 'Mn')
    title = re.sub(r'[^\w\s]', '', title)
    title = re.sub(r'\s+', ' ', title)
    title = title.strip()
    
    return title


def calculate_similarity(title1: str, title2: str) -> float:
    """Calcule la similarité entre deux titres (0-100%)."""
    if not title1 or not title2:
        return 0.0
    
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)
    
    if norm1 == norm2:
        return 100.0
    
    # Match sans espaces = 95%
    no_space1 = norm1.replace(' ', '')
    no_space2 = norm2.replace(' ', '')
    if no_space1 == no_space2:
        return 95.0
        
    # Similarité avec SequenceMatcher (0-90%)
    similarity = SequenceMatcher(None, norm1, norm2).ratio()
    return min(similarity * 90, 90.0)  # Max 90% pour éviter confusion avec match exact


async def get_all_tmdb_titles(tmdb_client, tmdb_id: int, media_type: str) -> List[str]:
    """Récupère TOUS les titres alternatifs d'un anime TMDB dans toutes les langues."""
    if not tmdb_client.api_key:
        return []
    
    try:
        # Requête pour récupérer les titres alternatifs
        endpoint = "tv" if media_type == "tv" else "movie"
        url = f"{tmdb_client.base_url}/{endpoint}/{tmdb_id}"
        params = {
            "api_key": tmdb_client.api_key,
            "language": "fr-FR",
            "append_to_response": "alternative_titles"
        }
        
        response = await tmdb_client.client.get(url, params=params)
        data = response.json()
        
        if not data:
            return []
        
        all_titles = set()  # Utiliser un set pour éviter les doublons
        
        # 1. Titre principal
        main_title = data.get("name") or data.get("title")
        if main_title:
            all_titles.add(main_title.strip())
        
        # 2. Titre original
        original_title = data.get("original_name") or data.get("original_title")
        if original_title:
            all_titles.add(original_title.strip())
        
        # 3. Récupérer le pays d'origine pour filtrage intelligent
        origin_countries = data.get("origin_country", [])  # Ex: ["JP"] ou ["US", "GB"]
        
        # FALLBACK pour les FILMS : utiliser production_countries si pas d'origin_country
        if not origin_countries and media_type == "movie":
            production_countries = data.get("production_countries", [])
            origin_countries = [country.get("iso_3166_1") for country in production_countries if country.get("iso_3166_1")]
            logger.debug(f"Film sans origin_country - Utilisation production_countries: {origin_countries}")
        
        logger.debug(f"Pays d'origine TMDB ({media_type}): {origin_countries}")
        
        # 4. Titres alternatifs de toutes les langues
        alternative_titles = data.get("alternative_titles", {})
        # CORRECTION : TV utilise "results", Movies utilise "titles"
        titles_list = alternative_titles.get("results", []) if media_type == "tv" else alternative_titles.get("titles", [])
        
        # 5. Filtrage INTELLIGENT par langue/origine
        for title_data in titles_list:
            iso_country = title_data.get("iso_3166_1", "")
            title = title_data.get("title", "").strip()
            
            if not title:
                continue
                
            # FRANÇAIS
            if iso_country == "FR":
                all_titles.add(title)
                logger.debug(f"Titre FRANÇAIS ajouté: {title}")
            
            # ANGLAIS
            elif iso_country in {"US", "GB"}:
                all_titles.add(title)
                logger.debug(f"Titre ANGLAIS ajouté ({iso_country}): {title}")
            
            # ORIGINAL (dynamique selon origin_country)
            elif iso_country in origin_countries:
                all_titles.add(title)
                logger.debug(f"Titre ORIGINAL ajouté ({iso_country}): {title}")
            
            # Titres sans pays spécifié
            elif not iso_country:
                all_titles.add(title)
                logger.debug(f"Titre sans pays ajouté: {title}")
        
        # Convertir en liste et filtrer les titres vides
        final_titles = [title for title in all_titles if title and len(title.strip()) > 0]
        
        logger.log("TMDB", f"Récupéré {len(final_titles)} titres pour TMDB ID {tmdb_id} ({media_type}, origine: {origin_countries}): {final_titles}")
        return final_titles
        
    except Exception as e:
        logger.error(f"Erreur récupération titres alternatifs TMDB {tmdb_id}: {e}")
        return []


async def find_best_match(anime_title: str, tmdb_results: List[Dict[str, Any]], tmdb_client) -> Optional[Dict[str, Any]]:
    """Trouve le meilleur match TMDB pour un titre d'anime donné."""
    if not tmdb_results:
        return None
    
    # Si un seul résultat, pas besoin de scoring
    if len(tmdb_results) == 1:
        result = tmdb_results[0]
        display_name = result.get("name") or result.get("title", "")
        logger.log("TMDB", f"Un seul résultat - Sélection automatique: {display_name}")
        return result
    
    # Plusieurs résultats → Scoring intelligent avec TOUS les titres
    logger.log("TMDB", f"Scoring intelligent avancé sur {len(tmdb_results)} résultats pour: {anime_title}")
    
    best_match = None
    best_score = 0.0
    
    for result in tmdb_results:
        tmdb_id = result.get("id")
        media_type = "tv" if "name" in result else "movie"
        
        # Récupérer TOUS les titres alternatifs
        all_tmdb_titles = await get_all_tmdb_titles(tmdb_client, tmdb_id, media_type)
        
        if not all_tmdb_titles:
            # Fallback sur les titres de base si échec
            all_tmdb_titles = []
            main_title = result.get("name") or result.get("title")
            if main_title:
                all_tmdb_titles.append(main_title)
            original_title = result.get("original_name") or result.get("original_title")
            if original_title and original_title != main_title:
                all_tmdb_titles.append(original_title)
        
        # Calculer le score pour CHAQUE titre TMDB
        max_score = 0.0
        best_matching_title = ""
        
        for tmdb_title in all_tmdb_titles:
            score = calculate_similarity(anime_title, tmdb_title)
            if score > max_score:
                max_score = score
                best_matching_title = tmdb_title
        
        # Logger le résultat du scoring
        display_name = result.get("name") or result.get("title", "")
        logger.log("TMDB", f"Score {max_score:.1f}% - {display_name} (meilleur match: '{best_matching_title}' parmi {len(all_tmdb_titles)} titres)")
        
        # Mise à jour du meilleur match
        if max_score > best_score:
            best_score = max_score
            best_match = result
    
    if best_match:
        final_name = best_match.get("name") or best_match.get("title", "")
        logger.log("TMDB", f"MEILLEUR MATCH ({best_score:.1f}%): {final_name} pour '{anime_title}'")
    else:
        logger.log("TMDB", f"Aucun match satisfaisant trouvé pour: {anime_title}")
    
    return best_match


class TMDBClient:
    """Client pour l'API TMDB avec cache intégré."""
    
    def __init__(self, client: HttpClient, api_key: Optional[str] = None):
        self.client = client
        self.api_key = api_key or settings.TMDB_API_KEY
        self.base_url = "https://api.themoviedb.org/3"
        self.image_base_url = "https://image.tmdb.org/t/p"
        
    async def search_anime(self, title: str) -> Optional[Dict[str, Any]]:
        """Recherche un anime sur TMDB dans le genre Animation uniquement."""
        cache_key = f"tmdb:search:{title.lower()}"
        
        # Vérifier le cache
        cached_data = await get_metadata_from_cache(cache_key)
        if cached_data:
            logger.log("TMDB", f"Cache hit pour recherche: {title}")
            return cached_data
        
        if not self.api_key:
            logger.warning("Aucune clé API TMDB configurée")
            return None
            
        try:
            # Recherche STRICTE - Animation UNIQUEMENT
            url = f"{self.base_url}/search/tv"
            params = {
                "api_key": self.api_key,
                "query": title,
                "language": "fr-FR"
            }
            
            response = await self.client.get(url, params=params)
            data = response.json()
            if not data or "results" not in data:
                return None
                
            results = data["results"]
            
            # FILTRAGE STRICT : Animation UNIQUEMENT (genre_ids contient 16)
            animation_results = []
            if results:
                for result in results:
                    genre_ids = result.get("genre_ids", [])
                    if 16 in genre_ids:  # 16 = Animation
                        animation_results.append(result)
                        logger.log("TMDB", f"Candidat série animation: {result.get('name')} (genres: {genre_ids})")
            else:
                logger.log("TMDB", f"Aucune série trouvée pour: {title}")
            
            if not animation_results:
                logger.log("TMDB", f"Aucune série d'animation trouvée pour: {title}, essai des films...")
                
                # FALLBACK : Chercher dans les films d'animation
                movie_url = f"{self.base_url}/search/movie"
                movie_response = await self.client.get(movie_url, params=params)
                movie_data = movie_response.json()
                
                if movie_data and "results" in movie_data:
                    movie_results = movie_data["results"]
                    
                    # Filtrer les films d'animation
                    for result in movie_results:
                        genre_ids = result.get("genre_ids", [])
                        if 16 in genre_ids:  # 16 = Animation
                            animation_results.append(result)
                            logger.log("TMDB", f"Film d'animation trouvé: {result.get('title')} (genres: {genre_ids})")
                
                if not animation_results:
                    logger.log("TMDB", f"Aucun anime/film d'animation trouvé pour: {title}")
                    return None
            
            # SYSTÈME DE MATCHING INTELLIGENT AVANCÉ
            best_match = await find_best_match(title, animation_results, self)
            if not best_match:
                logger.log("TMDB", f"Aucun match satisfaisant trouvé pour: {title}")
                return None
            
            final_display_name = best_match.get("name") or best_match.get("title", "")
            logger.log("TMDB", f"ANIME SÉLECTIONNÉ: {final_display_name} (ID: {best_match.get('id')}) - Animation validée")
            
            
            # Ajouter le type (tv ou movie) pour get_anime_details
            if "name" in best_match:
                best_match["media_type"] = "tv"
            else:
                best_match["media_type"] = "movie"
            
            # Mettre en cache pour 7 jours
            await set_metadata_to_cache(cache_key, best_match, settings.TMDB_TTL)
            return best_match
            
        except Exception as e:
            logger.error(f"Erreur recherche TMDB pour '{title}': {e}")
            return None
    
    async def get_anime_details(self, tmdb_id: int, media_type: str = "tv") -> Optional[Dict[str, Any]]:
        """Récupère les détails complets d'un anime/film depuis TMDB."""
        cache_key = f"tmdb:{tmdb_id}"
        
        # Vérifier le cache
        cached_data = await get_metadata_from_cache(cache_key)
        if cached_data:
            logger.log("TMDB", f"Cache hit pour détails: {tmdb_id}")
            return cached_data
            
        if not self.api_key:
            return None
            
        try:
            # Utiliser l'endpoint approprié selon le type de média
            endpoint = "tv" if media_type == "tv" else "movie"
            url = f"{self.base_url}/{endpoint}/{tmdb_id}"
            params = {
                "api_key": self.api_key,
                "language": "fr-FR",
                "append_to_response": "videos,images,credits,external_ids",  # Besoin d'external_ids pour IMDB ID
                "include_image_language": "fr,en,null"  # Inclure logos français, anglais et sans langue
            }
            
            logger.log("TMDB", f"Récupération détails {media_type.upper()}: {tmdb_id}")
            
            response = await self.client.get(url, params=params)
            data = response.json()
            if not data:
                return None
                
            logger.log("TMDB", f"Détails récupérés pour ID: {tmdb_id}")
            
            # Mettre en cache pour 7 jours
            await set_metadata_to_cache(cache_key, data, settings.TMDB_TTL)
            return data
            
        except Exception as e:
            logger.error(f"Erreur détails TMDB pour ID {tmdb_id}: {e}")
            return None
    
    async def get_season_details(self, tmdb_id: int, season_number: int) -> Optional[Dict[str, Any]]:
        """Récupère les détails d'une saison spécifique."""
        cache_key = f"tmdb:{tmdb_id}:s{season_number}"
        
        # Vérifier le cache
        cached_data = await get_metadata_from_cache(cache_key)
        if cached_data:
            logger.log("TMDB", f"Cache hit pour saison: {tmdb_id}:S{season_number}")
            return cached_data
            
        if not self.api_key:
            return None
            
        try:
            url = f"{self.base_url}/tv/{tmdb_id}/season/{season_number}"
            params = {
                "api_key": self.api_key,
                "language": "fr-FR"
            }
            
            response = await self.client.get(url, params=params)
            data = response.json()
            if not data:
                return None
                
            logger.log("TMDB", f"Saison récupérée: {tmdb_id}:S{season_number}")
            
            # Mettre en cache pour 7 jours
            await set_metadata_to_cache(cache_key, data, settings.TMDB_TTL)
            return data
            
        except Exception as e:
            logger.error(f"Erreur saison TMDB {tmdb_id}:S{season_number}: {e}")
            return None
    
    def get_image_url(self, path: str, size: str = "w500") -> str:
        """Construit l'URL complète d'une image TMDB."""
        if not path:
            return ""
        return f"{self.image_base_url}/{size}{path}"
    
    def get_poster_url(self, path: str) -> str:
        """URL du poster en HAUTE RÉSOLUTION."""
        return self.get_image_url(path, "w780")  # Plus haute résolution pour les posters
    
    def get_backdrop_url(self, path: str) -> str:
        """URL du backdrop en HAUTE RÉSOLUTION."""
        return self.get_image_url(path, "w1280")  # Plus haute résolution pour les backgrounds
    
    def get_logo_url(self, path: str) -> str:
        """URL du logo en HAUTE RÉSOLUTION."""
        return self.get_image_url(path, "w500")  # Plus haute résolution pour les logos
    
    def get_episode_image_url(self, path: str) -> str:
        """URL de l'image d'épisode en HAUTE RÉSOLUTION."""
        return self.get_image_url(path, "w500")  # Plus haute résolution pour les épisodes
    
    def extract_trailer_id(self, videos_data: Dict[str, Any]) -> Optional[str]:
        """Extrait l'ID vidéo YouTube du trailer depuis les données vidéos TMDB (format Stremio)."""
        if not videos_data:
            return None
        
        # Les données peuvent être soit directement une liste, soit avec "results"
        video_list = videos_data.get("results", videos_data) if isinstance(videos_data, dict) else videos_data
        
        if not isinstance(video_list, list):
            return None
            
        for video in video_list:
            if (video.get("type") == "Trailer" and 
                video.get("site") == "YouTube"):
                return video.get("key")  # Retourne seulement l'ID vidéo, pas l'URL complète
        
        return None
    
