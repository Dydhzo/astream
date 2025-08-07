from typing import List, Optional, Dict, Any
import asyncio

from astream.utils.logger import logger
from astream.utils.dependencies import get_animesama_api, get_animesama_player, get_global_http_client
from astream.utils.parsers import MediaIdParser
from astream.scrapers.animesama.details import get_or_fetch_anime_details
from astream.scrapers.animesama.video_resolver import AnimeSamaVideoResolver
from astream.utils.data.loader import get_dataset_loader
from astream.utils.data.database import get_metadata_from_cache, set_metadata_to_cache
from astream.config.settings import settings
from astream.utils.stremio_formatter import format_stream_for_stremio
from astream.scrapers.animesama.helpers import parse_genres_string


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
                logger.log("ANIMESAMA", f"Recherche '{search}' (genre: {genre}, langue: {language})")
                return await animesama_api.search_anime(search, language, genre)
            else:
                logger.log("ANIMESAMA", "Récupération contenu homepage complet")
                return await animesama_api.get_homepage_content()
                
        except Exception as e:
            logger.error(f"ANIMESAMA: Erreur récupération catalogue: {e}")
            return []

    async def get_anime_metadata(self, anime_id: str, client_ip: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Récupère métadonnées complètes d'un anime."""
        try:
            if not anime_id.startswith('as:'):
                logger.error(f"ID anime invalide: {anime_id}")
                return None
            
            anime_slug = anime_id.replace('as:', '')
            logger.log("ANIMESAMA", f"Récupération métadonnées pour {anime_slug}")
            
            animesama_api = await get_animesama_api()
            if client_ip:
                animesama_api.set_client_ip(client_ip)
            
            anime_data = await get_or_fetch_anime_details(animesama_api.details, anime_slug)
            
            if not anime_data:
                logger.warning(f"ANIMESAMA: Aucune donnée trouvée pour {anime_slug}")
                return None
            
            return await self._enrich_metadata_with_episode_counts(anime_data, client_ip)
            
        except Exception as e:
            logger.error(f"ANIMESAMA: Erreur récupération métadonnées {anime_id}: {e}")
            return None

    async def get_episode_streams(self, episode_id: str, language_filter: Optional[str] = None, language_order: Optional[str] = None, client_ip: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Récupère streams pour un épisode avec fusion dataset + scraping."""
        try:
            parsed_id = MediaIdParser.parse_episode_id(episode_id)
            if not parsed_id or parsed_id['is_metadata_only']:
                logger.error(f"Episode_id invalide ou métadonnées seulement: {episode_id}")
                return []
            
            anime_slug = parsed_id['anime_slug']
            season_number = parsed_id['season_number'] 
            episode_number = parsed_id['episode_number']
            
            logger.log("STREAM", f"Récupération streams {anime_slug} S{season_number}E{episode_number}")
            
            # 1. Vérifier cache des URLs de player fusionnées d'abord
            cache_key = f"as:{anime_slug}:s{season_number}e{episode_number}"
            cached_players = await get_metadata_from_cache(cache_key)
            
            if cached_players:
                logger.log("DATABASE", f"Cache hit {cache_key} - Players fusionnés récupérés")
                # Extraire URLs vidéo depuis le cache
                player_urls_with_language = cached_players.get("player_urls", [])
                
                if player_urls_with_language:
                    # Obtenir le resolver pour extraire les URLs vidéo
                    http_client = await self._get_http_client()
                    resolver = AnimeSamaVideoResolver(http_client)
                    
                    logger.log("DATABASE", f"Extraction vidéos depuis {len(player_urls_with_language)} URLs en cache")
                    
                    # Extraire les vraies URLs vidéo depuis les players en cache
                    video_urls_with_language = await resolver.extract_video_urls_from_players_with_language(
                        player_urls_with_language, config
                    )
                    
                    # Formater les streams au format attendu par Stremio
                    unique_streams = []
                    for video_data in video_urls_with_language:
                        video_url = video_data.get("url", "")
                        language = video_data.get("language", "VOSTFR")
                        
                        unique_streams.append(
                            format_stream_for_stremio(video_url, language, anime_slug, season_number)
                        )
                    
                    logger.log("STREAM", f"Cache: {len(unique_streams)} streams extraits depuis cache")
                    
                    # Appliquer filtrage et tri sur les streams depuis cache
                    unique_streams = self._filter_streams_by_language(unique_streams, language_filter, language_order)
                else:
                    unique_streams = []
            else:
                logger.log("DATABASE", f"Cache miss {cache_key} - Extraction dataset + scraping puis fusion")
                
                # 2. Lancer dataset + scraping EN PARALLÈLE (URLs de player seulement)
                dataset_task = asyncio.create_task(self._get_dataset_player_urls(anime_slug, season_number, episode_number, language_filter))
                scraping_task = asyncio.create_task(self._get_scraping_player_urls(anime_slug, season_number, episode_number, language_filter, client_ip, config))
                
                # 3. Attendre les 2 résultats
                dataset_players, scraping_players = await asyncio.gather(dataset_task, scraping_task, return_exceptions=True)
                
                # 4. Gérer les exceptions
                if isinstance(dataset_players, Exception):
                    logger.warning(f"DATASET: Erreur récupération players: {dataset_players}")
                    dataset_players = []
                
                if isinstance(scraping_players, Exception):
                    logger.warning(f"ANIMESAMA: Erreur récupération players: {scraping_players}")
                    scraping_players = []
                
                # 5. Fusionner les URLs de player
                all_players = dataset_players + scraping_players
                
                # 6. Dédupliquer les URLs de player par URL
                seen_urls = set()
                unique_players = []
                for player in all_players:
                    url = player.get("url")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        unique_players.append(player)
                
                # 7. Sauvegarder les URLs de player fusionnées en cache
                cache_data = {
                    "player_urls": unique_players,
                    "anime_slug": anime_slug,
                    "season": season_number,
                    "episode": episode_number,
                    "language_filter": language_filter,
                    "total_players": len(unique_players)
                }
                await set_metadata_to_cache(cache_key, cache_data, ttl=settings.EPISODE_TTL)
                logger.log("DATABASE", f"Cache set {cache_key} - {len(unique_players)} players fusionnés (dataset + scraping)")
                
                # 8. Extraire URLs vidéo depuis les players fusionnés
                if unique_players:
                    http_client = await self._get_http_client()
                    resolver = AnimeSamaVideoResolver(http_client)
                    
                    logger.log("STREAM", f"Extraction vidéos depuis {len(unique_players)} URLs fusionnées")
                    
                    video_urls_with_language = await resolver.extract_video_urls_from_players_with_language(
                        unique_players, config
                    )
                    
                    # Formater les streams au format attendu par Stremio
                    unique_streams = []
                    for video_data in video_urls_with_language:
                        video_url = video_data.get("url", "")
                        language = video_data.get("language", "VOSTFR")
                        
                        unique_streams.append(
                            format_stream_for_stremio(video_url, language, anime_slug, season_number)
                        )
                    
                    logger.log("STREAM", f"Fusion: {len(dataset_players)} dataset + {len(scraping_players)} scraping = {len(unique_streams)} streams extraits")
                else:
                    unique_streams = []
            
            logger.log("STREAM", f"Résultat final: {len(unique_streams)} streams uniques")
            
            return self._filter_streams_by_language(unique_streams, language_filter, language_order)
            
        except Exception as e:
            logger.error(f"STREAM: Erreur récupération streams {episode_id}: {e}")
            return []

    async def get_film_title(self, anime_slug: str, episode_num: int, client_ip: Optional[str] = None) -> Optional[str]:
        """Récupère titre d'un film."""
        try:
            animesama_api = await get_animesama_api()
            if client_ip:
                animesama_api.set_client_ip(client_ip)
            
            return await animesama_api.get_film_title(anime_slug, episode_num)
            
        except Exception as e:
            logger.error(f"ANIMESAMA: Erreur récupération titre film {anime_slug}#{episode_num}: {e}")
            return None

    def extract_available_genres(self, catalog_data: List[Dict[str, Any]]) -> List[str]:
        """Extrait genres disponibles depuis données catalogue."""
        try:
            genres = set()
            
            for anime in catalog_data:
                anime_genres = anime.get('genres', '')
                if isinstance(anime_genres, str) and anime_genres:
                    genre_list = parse_genres_string(anime_genres)
                    genres.update(genre_list)
                elif isinstance(anime_genres, list):
                    genres.update(anime_genres)
            
            cleaned_genres = [g for g in genres if len(g) > 1 and g not in ['N/A', 'n/a', '']]
            return sorted(cleaned_genres)
            
        except Exception as e:
            logger.warning(f"Erreur extraction genres: {e}")
            return []


    async def _enrich_metadata_with_episode_counts(self, anime_data: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        """Enrichit métadonnées avec comptage parallèle des épisodes par saison."""
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
                    logger.warning(f"ANIMESAMA: Erreur comptage épisodes saison {season_data.get('season_number')}: {e}")
                    season_data = season_data.copy()
                    season_data['episode_counts'] = {}
                    season_data['total_episodes'] = 0
                    return season_data
            
            enriched_seasons = await asyncio.gather(*[count_season_episodes(season) for season in seasons])
            
            enriched_anime_data = anime_data.copy()
            enriched_anime_data['seasons'] = enriched_seasons
            
            logger.debug(f"ANIMESAMA: Métadonnées enrichies {anime_slug}: {len(enriched_seasons)} saisons")
            return enriched_anime_data
            
        except Exception as e:
            logger.warning(f"ANIMESAMA: Erreur enrichissement métadonnées: {e}")
            return anime_data
    
    async def _get_dataset_player_urls(self, anime_slug: str, season: int, episode: int, language_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Récupère URLs de player depuis le dataset (sans cache)."""
        try:
            logger.log("DATASET", f"Extraction URLs player dataset pour {anime_slug} S{season}E{episode}")
            
            dataset_loader = get_dataset_loader()
            if not dataset_loader:
                logger.debug(f"DATASET: Loader non disponible")
                return []
            
            streams = await dataset_loader.get_streams(anime_slug, season, episode, language_filter)
            
            if not streams:
                return []
            
            # Retourner URLs de player au format standard
            player_urls_with_language = []
            for stream in streams:
                player_urls_with_language.append({
                    "url": stream.get("url", ""),
                    "language": stream.get("language", "VOSTFR").lower()
                })
            
            logger.log("DATASET", f"{len(player_urls_with_language)} URLs player dataset extraites")
            return player_urls_with_language
            
        except Exception as e:
            logger.error(f"DATASET: Erreur récupération URLs player: {e}")
            return []
    
    async def _get_scraping_player_urls(self, anime_slug: str, season: int, episode: int, language_filter: Optional[str] = None, client_ip: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Récupère URLs de player par scraping AnimeSama."""
        try:
            # Récupérer les détails de l'anime pour obtenir les données de saison
            animesama_api = await get_animesama_api()
            if client_ip:
                animesama_api.set_client_ip(client_ip)
                
            anime_data = await get_or_fetch_anime_details(animesama_api.details, anime_slug)
            if not anime_data:
                logger.warning(f"ANIMESAMA: Aucune donnée trouvée pour {anime_slug}")
                return []
            
            # Trouver la saison correspondante
            seasons = anime_data.get("seasons", [])
            target_season = None
            
            for season_data in seasons:
                if season_data.get("season_number") == season:
                    target_season = season_data
                    break
            
            if not target_season:
                logger.warning(f"ANIMESAMA: Saison {season} introuvable pour {anime_slug}")
                return []
            
            # Utiliser AnimeSamaPlayerExtractor pour extraire juste les URLs de player
            animesama_player = await get_animesama_player()
            if client_ip:
                animesama_player.set_client_ip(client_ip)
            
            player_urls = await animesama_player.extractor.extract_player_urls_smart_mapping_with_language(
                anime_slug=anime_slug,
                season_data=target_season,
                episode_number=episode,
                language_filter=language_filter,
                config=config
            )
            
            if player_urls:
                logger.log("ANIMESAMA", f"{len(player_urls)} URLs player scrapées pour {anime_slug} S{season}E{episode}")
            
            return player_urls
            
        except Exception as e:
            logger.error(f"ANIMESAMA: Erreur scraping URLs player: {e}")
            return []
    
    def _filter_streams_by_language(self, streams: List[Dict[str, Any]], language_filter: Optional[str] = None, language_order: Optional[str] = None) -> List[Dict[str, Any]]:
        """Filtre et trie les streams par langue selon l'ordre de priorité."""
        if not language_filter or language_filter == "Tout":
            # Trier selon l'ordre de priorité si spécifié
            if language_order:
                return self._sort_streams_by_language_priority(streams, language_order)
            return streams
        
        filtered_streams = []
        for stream in streams:
            stream_lang = stream.get("language", "").upper()
            
            if language_filter == "VOSTFR" and stream_lang == "VOSTFR":
                filtered_streams.append(stream)
            elif language_filter == "VF" and stream_lang in ["VF", "VF1", "VF2"]:
                filtered_streams.append(stream)
        
        return filtered_streams
    
    def _sort_streams_by_language_priority(self, streams: List[Dict[str, Any]], language_order: str) -> List[Dict[str, Any]]:
        """Trie les streams selon l'ordre de priorité des langues."""
        try:
            # Parse l'ordre des langues (ex: "VOSTFR,VF" ou "VF,VOSTFR")
            priority_langs = [lang.strip().upper() for lang in language_order.split(',')]
            
            def get_language_priority(stream):
                stream_lang = stream.get("language", "").upper()
                
                # Normaliser les variantes VF
                if stream_lang in ["VF1", "VF2"]:
                    stream_lang = "VF"
                
                try:
                    return priority_langs.index(stream_lang)
                except ValueError:
                    # Langue non trouvée = priorité la plus basse
                    return len(priority_langs)
            
            # Trier par priorité (index le plus bas = priorité la plus haute)
            sorted_streams = sorted(streams, key=get_language_priority)
            
            # Log détaillé du tri en mode debug uniquement
            languages_found = [stream.get("language", "UNKNOWN") for stream in sorted_streams]
            logger.debug(f"Streams triés: {language_order} -> {languages_found[:3]}{'...' if len(languages_found) > 3 else ''}")
            
            return sorted_streams
            
        except Exception as e:
            logger.warning(f"Erreur tri langues '{language_order}': {e}")
            return streams
    
    async def _get_http_client(self):
        """Récupère le client HTTP global."""
        return get_global_http_client()