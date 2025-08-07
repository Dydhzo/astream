from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from urllib.parse import quote
import re
import asyncio

from astream.config.settings import settings, web_config
from astream.utils.validation.helpers import validate_config
from astream.scrapers.animesama.client import AnimeSamaAPI
from astream.scrapers.animesama.details import get_or_fetch_anime_details
from astream.scrapers.animesama.player import AnimeSamaPlayer
from astream.utils.logger import logger
from astream.utils.data.database import get_metadata_from_cache, set_metadata_to_cache
from astream.utils.dependencies import get_animesama_api_dependency, get_animesama_player_dependency, extract_client_ip, get_tmdb_service
from astream.utils.errors.handler import global_exception_handler, AnimeNotFoundException
from astream.services.anime import AnimeSamaService
from astream.scrapers.animesama.helpers import parse_genres_string
from astream.integrations.tmdb.service import TMDBService
from astream.utils.validation.models import ConfigModel

# Configuration des templates et router
templates = Jinja2Templates("astream/templates")
main = APIRouter()


def _build_genre_links(request: Request, b64config: str, genres: list) -> list:
    """Construit les liens de genre pour Stremio."""
    if not genres:
        return []  # Aucun genre disponible
    genre_links = []  # Liste des liens de genres
    base_url = str(request.base_url).rstrip('/')
    if b64config:
        encoded_manifest = f"{base_url}/{b64config}/manifest.json"
    else:
        encoded_manifest = f"{base_url}/manifest.json"

    encoded_manifest = quote(encoded_manifest, safe='')

    for genre_name in genres:
        genre_links.append({
            "name": genre_name,
            "category": "Genres",
            "url": f"stremio:///discover/{encoded_manifest}/anime/animesama_catalog?genre={quote(genre_name)}"
        })

    return genre_links


def _build_imdb_link(anime_data: dict) -> list:
    """Construit le lien IMDB cliquable (format FKStream)."""
    imdb_links = []
    
    imdb_id = anime_data.get('imdb_id')
    tmdb_rating = anime_data.get('tmdb_rating')
    
    if imdb_id and tmdb_rating:
        rating_display = str(tmdb_rating)
        imdb_links.append({
            "name": rating_display,  # Note affichée sur le bouton
            "category": "imdb",      # Catégorie reconnue par Stremio
            "url": f"https://imdb.com/title/{imdb_id}"  # URL IMDB
        })
        logger.log("TMDB", f"Lien IMDB créé: {rating_display} → {imdb_id}")
    elif imdb_id:
        # Pas de note mais on a l'IMDB ID
        imdb_links.append({
            "name": "IMDB",
            "category": "imdb",
            "url": f"https://imdb.com/title/{imdb_id}"
        })
        logger.log("TMDB", f"Lien IMDB créé sans note: {imdb_id}")
    
    return imdb_links


async def _apply_tmdb_enhancement(anime_data: dict, config: 'ConfigModel', tmdb_service: 'TMDBService', context: str = "") -> dict:
    """Applique l'enrichissement TMDB de façon sécurisée et cohérente."""
    if not config.tmdbEnabled or not (config.tmdbApiKey or settings.TMDB_API_KEY):
        return anime_data
    
    if not anime_data:
        return anime_data
    
    try:
        enhanced_data = await tmdb_service.enhance_anime_metadata(anime_data, config)
        anime_slug = anime_data.get('slug', 'unknown')
        logger.log("TMDB", f"Enrichissement TMDB réussi pour {context}: {anime_slug}")
        return enhanced_data
    except Exception as e:
        anime_slug = anime_data.get('slug', 'unknown')
        logger.error(f"Erreur enrichissement TMDB {context} pour {anime_slug}: {e}")
        return anime_data


async def _enrich_catalog_with_tmdb(anime_data: list, config: 'ConfigModel', tmdb_service: 'TMDBService') -> list:
    """Enrichit un catalogue d'anime avec TMDB en parallèle."""
    if not config.tmdbEnabled or not (config.tmdbApiKey or settings.TMDB_API_KEY):
        return anime_data
    
    try:
        tasks = [tmdb_service.enhance_anime_metadata(anime, config) for anime in anime_data]
        enhanced_anime_data = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filtrer les exceptions
        enhanced_anime_data = [
            result if not isinstance(result, Exception) else anime_data[i]
            for i, result in enumerate(enhanced_anime_data)
        ]
        logger.log("TMDB", f"Catalogue enrichi avec TMDB: {len([r for r in enhanced_anime_data if 'poster' in r])} anime")
        return enhanced_anime_data
    except Exception as e:
        logger.error(f"Erreur enrichissement TMDB catalogue: {e}")
        return anime_data


async def _detect_episodes_for_season(season: dict, anime_slug: str, animesama_player) -> tuple:
    """Détecte le nombre d'épisodes disponibles pour une saison."""
    season_number = season.get('season_number')
    try:
        episode_counts_dict = await animesama_player.get_available_episodes_count(anime_slug, season)
        available_episodes = max(episode_counts_dict.values()) if episode_counts_dict else 0
        
        if available_episodes > 0:
            return season_number, available_episodes
        else:
            # Fallback basé sur le type de saison
            return season_number, _get_default_episode_count(season_number)
    except Exception as e:
        logger.warning(f"Impossible de détecter le nombre d'épisodes pour {anime_slug} S{season_number}: {e}")
        return season_number, _get_default_episode_count(season_number)


def _get_default_episode_count(season_number: int) -> int:
    """Retourne un nombre d'épisodes par défaut basé sur le type de saison."""
    if season_number == 990:  # Films
        return 5
    elif season_number == 0:  # Spéciaux
        return 6
    elif season_number == 991:  # Hors-série
        return 4
    else:  # Saisons normales
        return 12


async def _build_episodes_mapping(seasons: list, anime_slug: str, animesama_player) -> dict:
    """Construit le mapping des épisodes disponibles par saison."""
    logger.log("API", f"Détection parallèle des épisodes pour {len(seasons)} saisons de {anime_slug}")
    detection_tasks = [_detect_episodes_for_season(season, anime_slug, animesama_player) for season in seasons]
    episodes_results = await asyncio.gather(*detection_tasks)
    return dict(episodes_results)


async def _create_tmdb_episodes_mapping(config: 'ConfigModel', enhanced_anime_data: dict, tmdb_service: 'TMDBService', tmdb_episodes_map: dict, seasons: list, episodes_map: dict) -> dict:
    """Crée le mapping intelligent TMDB des épisodes si activé."""
    if not (config.tmdbEnabled and config.tmdbEpisodeMapping and tmdb_episodes_map):
        return {}
    
    try:
        from astream.integrations.tmdb.episode_mapper import create_intelligent_episode_mapping
        intelligent_tmdb_map = create_intelligent_episode_mapping(tmdb_episodes_map, seasons, episodes_map)
        logger.log("TMDB", f"Mapping intelligent créé: {len(intelligent_tmdb_map)} correspondances")
        return intelligent_tmdb_map
    except Exception as e:
        logger.error(f"Erreur création mapping intelligent: {e}")
        return {}


async def _build_videos_list(seasons: list, episodes_map: dict, intelligent_tmdb_map: dict, 
                           enhanced_anime_data: dict, anime_slug: str, animesama_api, config: 'ConfigModel') -> list:
    """Construit la liste des vidéos avec métadonnées TMDB si disponibles."""
    videos = []
    
    # Utiliser le mapping intelligent si disponible
    final_tmdb_map = intelligent_tmdb_map if intelligent_tmdb_map else {}
    if final_tmdb_map:
        logger.log("TMDB", f"Utilisation mapping intelligent: {len(final_tmdb_map)} correspondances")
    else:
        logger.log("TMDB", f"Aucun mapping épisodes utilisé (désactivé ou sécurité)")
    
    for season in seasons:
        season_number = season.get('season_number')
        season_name = season.get('name')
        max_episodes = episodes_map.get(season_number, 12)  # Fallback à 12 si problème
        
        for episode_num in range(1, max_episodes + 1):
            episode_title, episode_overview = await _get_episode_title_and_overview(
                season_number, episode_num, anime_slug, enhanced_anime_data, season_name, animesama_api
            )
            
            # Créer l'objet vidéo de base
            video = {
                "id": f"as:{anime_slug}:s{season_number}e{episode_num}",
                "title": episode_title,
                "season": season_number,
                "episode": episode_num,
                "thumbnail": enhanced_anime_data.get('image'),
                "overview": episode_overview
            }
            
            # Appliquer les métadonnées TMDB si disponibles
            _apply_tmdb_episode_metadata(video, final_tmdb_map, config, season_number, episode_num)
            
            videos.append(video)
    
    return videos


async def _get_episode_title_and_overview(season_number: int, episode_num: int, anime_slug: str, 
                                        enhanced_anime_data: dict, season_name: str, animesama_api) -> tuple:
    """Récupère le titre et la description d'un épisode selon le type de saison."""
    if season_number == 990:  # Films
        logger.log("API", f"FILM DETECTE - anime: {anime_slug}, saison: {season_number}, episode: {episode_num}")
        try:
            film_title = await animesama_api.get_film_title(anime_slug, episode_num)
            if film_title:
                episode_title = film_title
                episode_overview = enhanced_anime_data.get('synopsis', film_title)
                logger.log("API", f"FILM - Titre final utilisé: '{episode_title}'")
            else:
                episode_title = f"Film {episode_num}"
                episode_overview = enhanced_anime_data.get('synopsis', f"Film {episode_num}")
                logger.warning(f"FILM - Titre par défaut utilisé: '{episode_title}'")
        except Exception as e:
            logger.error(f"FILM - Erreur récupération titre {anime_slug} #{episode_num}: {e}")
            episode_title = f"Film {episode_num}"
            episode_overview = enhanced_anime_data.get('synopsis', f"Film {episode_num}")
    else:  # Épisodes normaux
        logger.debug(f"EPISODE - anime: {anime_slug}, saison: {season_number}, episode: {episode_num}")
        episode_title = f"Episode {episode_num}"
        episode_overview = enhanced_anime_data.get('synopsis', f"Episode {episode_num} de {season_name}")
    
    return episode_title, episode_overview


def _apply_tmdb_episode_metadata(video: dict, final_tmdb_map: dict, config: 'ConfigModel', 
                                season_number: int, episode_num: int):
    """Applique les métadonnées TMDB à un épisode si disponibles."""
    episode_key = f"s{season_number}e{episode_num}"
    
    if episode_key in final_tmdb_map:
        tmdb_episode = final_tmdb_map[episode_key]
        logger.log("TMDB", f"Épisode TMDB trouvé: S{season_number}E{episode_num}")
        
        # MÉTADONNÉES ÉPISODES - SEULEMENT SI MAPPING INTELLIGENT ACTIVÉ
        if config.tmdbEpisodeMapping and season_number > 0:
            # Images d'épisodes
            if tmdb_episode.get("still_path"):
                from astream.integrations.tmdb.client import TMDBClient
                temp_client = TMDBClient(None)
                video['thumbnail'] = temp_client.get_episode_image_url(tmdb_episode["still_path"])
                logger.log("TMDB", f"Image épisode TMDB appliquée: S{season_number}E{episode_num}")
            
            # Date de sortie épisode
            if tmdb_episode.get("air_date"):
                video['released'] = f"{tmdb_episode['air_date']}T00:00:00.000Z"
                logger.log("TMDB", f"Date sortie épisode TMDB: S{season_number}E{episode_num} - {tmdb_episode['air_date']}")
            
            # Titres d'épisodes
            if tmdb_episode.get("name"):
                video['title'] = tmdb_episode["name"]
                logger.log("TMDB", f"Titre épisode TMDB: S{season_number}E{episode_num} - {tmdb_episode['name']}")
                
            # Descriptions d'épisodes
            if tmdb_episode.get("overview") and len(tmdb_episode["overview"].strip()) > 10:
                video['overview'] = tmdb_episode["overview"]
                logger.log("TMDB", f"Description épisode TMDB: S{season_number}E{episode_num}")
        else:
            if season_number > 0:
                logger.log("TMDB", f"Mapping épisodes désactivé - données Anime-Sama conservées pour S{season_number}E{episode_num}")
    else:
        if season_number > 0:  # Log seulement pour saisons normales
            status = "intelligent" if config.tmdbEpisodeMapping else "TMDB direct"
            logger.log("TMDB", f"Épisode S{season_number}E{episode_num} pas dans le mapping {status}")


@main.get("/")
async def root():
    return RedirectResponse("/configure")


@main.get("/health")
async def health():
    """Endpoint de vérification de santé."""
    return {"status": "ok"}


@main.get("/configure")
@main.get("/{b64config}/configure")
async def configure(request: Request):
    """Affiche la page de configuration."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "CUSTOM_HEADER_HTML": settings.CUSTOM_HEADER_HTML or "",
            "EXCLUDED_DOMAINS": settings.EXCLUDED_DOMAINS or "",
            "webConfig": {**web_config, "ADDON_NAME": settings.ADDON_NAME},
        },
    )


@main.get("/manifest.json")
@main.get("/{b64config}/manifest.json")
async def manifest(request: Request, b64config: str = None, animesama_api: AnimeSamaAPI = Depends(get_animesama_api_dependency)):
    """Fournit le manifeste pour Stremio."""
    base_manifest = {
        "id": settings.ADDON_ID,
        "name": settings.ADDON_NAME,
        "description": f"{settings.ADDON_NAME} – Addon non officiel pour accéder au contenu d'Anime-Sama",
        "version": "2.0.0",
        "catalogs": [
            {
                "type": "anime",
                "id": "animesama_catalog",
                "name": "Anime-Sama",
                "extra": [
                    {"name": "skip"},
                    {"name": "search", "isRequired": False},
                    {"name": "genre", "isRequired": False, "options": []}
                ]
            }
        ],
        "resources": [
            "catalog",
            {"name": "meta", "types": ["anime"], "idPrefixes": ["as"]},
            {"name": "stream", "types": ["anime"], "idPrefixes": ["as"]}
        ],
        "types": ["anime"],
        "logo": "https://raw.githubusercontent.com/Dydhzo/astream/refs/heads/main/astream/assets/astream-logo.jpg",
        "background": "https://raw.githubusercontent.com/Dydhzo/astream/refs/heads/main/astream/assets/astream-background.png",
        "behaviorHints": {"configurable": True, "configurationRequired": False},
    }

    config = validate_config(b64config)
    if not config:
        base_manifest["name"] = "| AStream"
        base_manifest["description"] = (
            f"CONFIGURATION OBSELETE, VEUILLEZ RECONFIGURER SUR {request.url.scheme}://{request.url.netloc}"
        )
        return base_manifest

    language_extension = config.get("language", "Tout")
    if language_extension != "Tout":
        base_manifest["name"] = f"{settings.ADDON_NAME} | {language_extension}"
    else:
        base_manifest["name"] = settings.ADDON_NAME

    try:
        unique_genres = await extract_unique_genres(animesama_api)
        base_manifest["catalogs"][0]["extra"][2]["options"] = unique_genres
        logger.log("API", f"MANIFEST - Ajout de {len(unique_genres)} options de genre depuis le catalogue")
    except Exception as e:
        logger.error(f"MANIFEST - Echec de l'extraction des genres: {e}")

    return base_manifest


async def extract_unique_genres(animesama_api: AnimeSamaAPI) -> list[str]:
    """Extrait tous les genres uniques des données anime."""
    cached_data = await get_metadata_from_cache("as:homepage")

    if not cached_data:
        logger.debug("CACHE MISS: as:homepage - Recuperation depuis anime-sama")
        anime_data = await animesama_api.get_homepage_content()
        await set_metadata_to_cache("as:homepage", {"anime": anime_data, "total": len(anime_data)})
        logger.debug("CACHE SAUVEGARDE: as:homepage")
    else:
        logger.debug("CACHE HIT: as:homepage")
        anime_data = cached_data.get("anime", [])

    unique_genres = set()
    for anime in anime_data:
        genres_raw = anime.get('genres', '')
        if genres_raw:
            genres = parse_genres_string(genres_raw)
            unique_genres.update(genres)

    sorted_genres = sorted(list(unique_genres))

    logger.debug(f"GENRES - Extraction de {len(sorted_genres)} genres uniques depuis le cache catalog")
    return sorted_genres


@main.get("/catalog/anime/animesama_catalog.json")
@main.get("/{b64config}/catalog/anime/animesama_catalog.json")
@main.get("/catalog/anime/animesama_catalog/search={search}.json")
@main.get("/{b64config}/catalog/anime/animesama_catalog/search={search}.json")
@main.get("/catalog/anime/animesama_catalog/genre={genre}.json")
@main.get("/{b64config}/catalog/anime/animesama_catalog/genre={genre}.json")
@main.get("/catalog/anime/animesama_catalog/search={search}&genre={genre}.json")
@main.get("/{b64config}/catalog/anime/animesama_catalog/search={search}&genre={genre}.json")
async def animesama_catalog(request: Request, b64config: str = None, search: str = None, genre: str = None, tmdb_service: TMDBService = Depends(get_tmdb_service)):
    """Fournit le catalogue d'anime."""
    try:
        if not search and "search" in request.query_params:
            search = request.query_params.get("search")
        if not genre and "genre" in request.query_params:
            genre = request.query_params.get("genre")

        logger.log("API", f"CATALOG - Catalogue Anime-Sama demandé, recherche: {search}, genre: {genre}")

        # Configuration et IP client
        config_dict = validate_config(b64config) or {}
        config = ConfigModel(**config_dict)
        language_filter = config.language if config.language != "Tout" else None
        client_ip = extract_client_ip(request)
        
        # Service layer
        service = AnimeSamaService()
        anime_data = await service.get_catalog_data(search, genre, language_filter, client_ip)
        
        logger.log("API", f"Traitement de {len(anime_data)} anime.")

        metas = []
        
        # Enrichir en parallèle avec TMDB si activé
        enhanced_anime_data = await _enrich_catalog_with_tmdb(anime_data, config, tmdb_service)
        
        for anime in enhanced_anime_data:
            anime_title = anime.get('title', '').strip()
            anime_slug = anime.get('slug', '')
            
            # Protection: utiliser slug si pas de titre
            if not anime_title:
                anime_title = anime_slug.replace('-', ' ').title() if anime_slug else 'Titre indisponible'
                logger.warning(f"CATALOG - Pas de titre pour {anime_slug}, utilisation de '{anime_title}'")
            
            logger.debug(f"CATALOG - Anime: {anime_slug} -> Titre: '{anime_title}'")
            
            # IMPORTANT: Conserver les genres d'Anime-Sama (pas TMDB)
            genres_raw = anime.get('genres', '')
            genres = parse_genres_string(genres_raw) if isinstance(genres_raw, str) else genres_raw

            if genre and genre not in genres:
                continue

            genre_links = _build_genre_links(request, b64config, genres)
            imdb_links = _build_imdb_link(anime)  # Liens IMDB cliquables

            meta = {
                "id": f"as:{anime.get('slug')}",
                "type": "anime",
                "poster": anime.get('poster', anime.get('image')),  # TMDB prioritaire
                "posterShape": "poster",
                "background": anime.get('background', anime.get('image')),  # TMDB prioritaire
                "genres": genres,  # Toujours Anime-Sama
                "links": genre_links + imdb_links,  # Genres + IMDB
            }
            
            # DURÉE - ANNÉE - NOTE TMDB
            if anime.get('runtime'):  # Durée depuis TMDB
                meta["runtime"] = anime.get('runtime')
            if anime.get('year_range') or anime.get('year'):  # Année depuis TMDB
                meta["releaseInfo"] = anime.get('year_range', anime.get('year'))
            if anime.get('imdbRating'):  # Note TMDB affichée
                meta["imdbRating"] = anime.get('imdbRating')
            
            # LOGO STREMIO (méthode FKStream - propriété officielle) - DEBUG
            if anime.get('logo'):
                logo_url = anime.get('logo')
                meta["logo"] = logo_url  # Propriété officielle Stremio
                meta["name"] = anime_title  # Titre obligatoire
                logger.log("TMDB", f"Logo Stremio ajouté CATALOGUE pour {anime_title}: {logo_url}")
            else:
                meta["name"] = anime_title  # Titre normal
                logger.log("TMDB", f"Pas de logo CATALOGUE pour: {anime_title}")
            
            # DESCRIPTION dans le catalogue (TMDB prioritaire)
            if anime.get('description'):
                meta["description"] = anime.get('description')
            elif anime.get('synopsis'):
                meta["description"] = anime.get('synopsis')
            
            # TRAILERS si disponible (TMDB - format Stremio)
            if anime.get('trailers'):
                meta["trailers"] = anime.get('trailers')  # Déjà au bon format depuis TMDB
            
            # Durée, année et IMDB déjà gérés dans meta ci-dessus
            
            metas.append(meta)

        if search and genre:
            logger.log("API", f"CATALOG - Recherche '{search}' + Genre '{genre}': {len(metas)} anime trouvés")
        elif search:
            logger.log("API", f"CATALOG - Recherche '{search}': {len(metas)} anime trouvés")
        elif genre:
            logger.log("API", f"CATALOG - Genre '{genre}': {len(metas)} anime trouvés")
        else:
            logger.log("API", f"CATALOG - Retour de tous les {len(metas)} anime valides")

        return {"metas": metas}
        
    except Exception as e:
        logger.error(f"Erreur dans le catalogue: {e}")
        raise AnimeNotFoundException(f"Erreur catalogue: {str(e)}")


@main.get("/meta/anime/{id}.json")
@main.get("/{b64config}/meta/anime/{id}.json")
async def animesama_meta(request: Request, id: str, b64config: str = None, animesama_api: AnimeSamaAPI = Depends(get_animesama_api_dependency), animesama_player: AnimeSamaPlayer = Depends(get_animesama_player_dependency), tmdb_service: TMDBService = Depends(get_tmdb_service)):
    """Fournit les métadonnées détaillées d'un anime."""
    if not id.startswith("as:"):
        return {"meta": {}}

    anime_slug = id.replace("as:", "")

    anime_data = await get_or_fetch_anime_details(animesama_api.details, anime_slug)

    if not anime_data:
        return {"meta": {}}

    # Configuration utilisateur
    config_dict = validate_config(b64config) or {}
    config = ConfigModel(**config_dict)
    
    # Enrichir avec TMDB si activé
    enhanced_anime_data = await _apply_tmdb_enhancement(anime_data, config, tmdb_service, "métadonnées")
    
    meta = {
        "id": f"as:{enhanced_anime_data.get('slug')}",
        "type": "anime",
        "poster": enhanced_anime_data.get('poster', enhanced_anime_data.get('image')),
        "posterShape": "poster", 
        "background": enhanced_anime_data.get('background', enhanced_anime_data.get('image')),
        "description": enhanced_anime_data.get('description', enhanced_anime_data.get('synopsis', 'Aucune description disponible')),
        "genres": enhanced_anime_data.get('genres', []) if isinstance(enhanced_anime_data.get('genres'), list) else [],
        "behaviorHints": {
            "hasScheduledVideos": True
        }
    }
    
    # DURÉE - ANNÉE - NOTE TMDB
    if enhanced_anime_data.get('runtime'):  # Durée depuis TMDB
        meta["runtime"] = enhanced_anime_data.get('runtime')
    if enhanced_anime_data.get('year_range') or enhanced_anime_data.get('year'):  # Année depuis TMDB
        meta["releaseInfo"] = enhanced_anime_data.get('year_range', enhanced_anime_data.get('year'))
    if enhanced_anime_data.get('imdbRating'):  # Note TMDB affichée
        meta["imdbRating"] = enhanced_anime_data.get('imdbRating')
    
    # LOGO STREMIO dans les détails (propriété officielle) - DEBUG
    if enhanced_anime_data.get('logo'):
        logo_url = enhanced_anime_data.get('logo')
        meta["logo"] = logo_url  # Propriété officielle Stremio
        meta["name"] = enhanced_anime_data.get('title', anime_slug.replace('-', ' ').title())  # Titre obligatoire
        logger.log("TMDB", f"Logo détails pour {anime_slug}")
    else:
        meta["name"] = enhanced_anime_data.get('title', anime_slug.replace('-', ' ').title())
    
    # TRAILERS si disponible (format Stremio)
    if enhanced_anime_data.get('trailers'):
        meta["trailers"] = enhanced_anime_data.get('trailers')  # Déjà au bon format depuis TMDB
    
    # ANNÉES avec système début-fin
    if enhanced_anime_data.get('year_range'):
        meta["releaseInfo"] = enhanced_anime_data.get('year_range')
    elif enhanced_anime_data.get('year'):
        meta["releaseInfo"] = enhanced_anime_data.get('year')

    # Récupérer le mapping des épisodes TMDB
    tmdb_episodes_map = {}
    if config.tmdbEnabled and (config.tmdbApiKey or settings.TMDB_API_KEY):
        try:
            tmdb_episodes_map = await tmdb_service.get_episodes_mapping(enhanced_anime_data, config)
            logger.log("TMDB", f"Mapping épisodes TMDB récupéré: {len(tmdb_episodes_map)} épisodes")
        except Exception as e:
            logger.error(f"Erreur récupération mapping épisodes: {e}")
            tmdb_episodes_map = {}

    seasons = enhanced_anime_data.get("seasons", [])
    episodes_map = await _build_episodes_mapping(seasons, anime_slug, animesama_player)
    
    # Créer le mapping intelligent TMDB si activé
    intelligent_tmdb_map = await _create_tmdb_episodes_mapping(
        config, enhanced_anime_data, tmdb_service, tmdb_episodes_map, seasons, episodes_map
    )
    
    # Générer les vidéos avec les métadonnées appropriées
    videos = await _build_videos_list(
        seasons, episodes_map, intelligent_tmdb_map, enhanced_anime_data, 
        anime_slug, animesama_api, config
    )
    
    meta['videos'] = videos

    # Add links - IMPORTANT: Utiliser les genres d'Anime-Sama (non TMDB)
    genres = anime_data.get('genres', [])  # Toujours utiliser anime_data original
    if isinstance(genres, str):
        genres = parse_genres_string(genres)
    meta['genres'] = genres
    
    genre_links = _build_genre_links(request, b64config, genres)
    imdb_links = _build_imdb_link(enhanced_anime_data)  # Liens IMDB cliquables
    meta['links'] = genre_links + imdb_links  # Genres + IMDB

    return {"meta": meta}