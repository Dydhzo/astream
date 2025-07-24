from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from urllib.parse import quote
import re
import asyncio

from astream.config.app_settings import settings, web_config
from astream.utils.config_validator import config_check
from astream.scrapers.animesama import AnimeSamaAPI
from astream.scrapers.animesama_details import get_or_fetch_anime_details
from astream.scrapers.animesama_player import AnimeSamaPlayer
from astream.utils.logger import logger
from astream.utils.database import get_metadata_from_cache, set_metadata_to_cache
from astream.utils.dependencies import get_animesama_api_dependency, get_animesama_player_dependency, extract_client_ip
from astream.utils.error_handler import global_exception_handler, AnimeNotFoundException
from astream.utils.animesama_service import AnimeSamaService

templates = Jinja2Templates("astream/templates")
main = APIRouter()


def _build_genre_links(request: Request, b64config: str, genres: list) -> list:
    """Construit les liens de genre pour Stremio."""
    if not genres:
        return []
    genre_links = []
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
            "EXCLUDED_DOMAINS": settings.EXCLUDED_DOMAIN or "",
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
        "version": "1.0.0",
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

    config = config_check(b64config)
    if not config:
        base_manifest["name"] = "❌ | AStream"
        base_manifest["description"] = (
            f"⚠️ CONFIGURATION OBSELETE, VEUILLEZ RECONFIGURER SUR {request.url.scheme}://{request.url.netloc} ⚠️"
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
        logger.info(f"📋 MANIFEST - Ajout de {len(unique_genres)} options de genre depuis le catalogue")
    except Exception as e:
        logger.error(f"❌ MANIFEST - Echec de l'extraction des genres: {e}")

    return base_manifest


async def extract_unique_genres(animesama_api: AnimeSamaAPI) -> list[str]:
    """Extrait tous les genres uniques des données anime."""
    cached_data = await get_metadata_from_cache("as:homepage:content")

    if not cached_data:
        logger.debug("📦 CACHE MISS: as:homepage:content - Recuperation depuis anime-sama")
        animes_data = await animesama_api.get_homepage_content()
        await set_metadata_to_cache("as:homepage:content", {"animes": animes_data, "total": len(animes_data)})
        logger.debug("✅ CACHE SAUVEGARDE: as:homepage:content")
    else:
        logger.debug("✅ CACHE HIT: as:homepage:content")
        animes_data = cached_data.get("animes", [])

    unique_genres = set()
    for anime in animes_data:
        genres_raw = anime.get('genres', '')
        if genres_raw:
            genres = [g.strip() for g in genres_raw.split(',') if g.strip()]
            unique_genres.update(genres)

    sorted_genres = sorted(list(unique_genres))

    logger.debug(f"🎭 GENRES - Extraction de {len(sorted_genres)} genres uniques depuis le cache catalog")
    return sorted_genres


@main.get("/catalog/anime/animesama_catalog.json")
@main.get("/{b64config}/catalog/anime/animesama_catalog.json")
@main.get("/catalog/anime/animesama_catalog/search={search}.json")
@main.get("/{b64config}/catalog/anime/animesama_catalog/search={search}.json")
@main.get("/catalog/anime/animesama_catalog/genre={genre}.json")
@main.get("/{b64config}/catalog/anime/animesama_catalog/genre={genre}.json")
@main.get("/catalog/anime/animesama_catalog/search={search}&genre={genre}.json")
@main.get("/{b64config}/catalog/anime/animesama_catalog/search={search}&genre={genre}.json")
async def animesama_catalog(request: Request, b64config: str = None, search: str = None, genre: str = None):
    """Fournit le catalogue d'animes."""
    try:
        if not search and "search" in request.query_params:
            search = request.query_params.get("search")
        if not genre and "genre" in request.query_params:
            genre = request.query_params.get("genre")

        logger.info(f"🔍 CATALOG - Catalogue Anime-Sama demandé, recherche: {search}, genre: {genre}")

        # Configuration et IP client
        config = config_check(b64config)
        language_filter = config.get("language") if config and config.get("language") != "Tout" else None
        client_ip = extract_client_ip(request)
        
        # Service layer
        service = AnimeSamaService()
        animes_data = await service.get_catalog_data(search, genre, language_filter, client_ip)
        
        logger.info(f"Traitement de {len(animes_data)} animes.")

        config = config_check(b64config)

        metas = []
        for anime in animes_data:
            anime_title = anime.get('title', '').strip()
            anime_slug = anime.get('slug', '')
            
            # Protection: utiliser slug si pas de titre
            if not anime_title:
                anime_title = anime_slug.replace('-', ' ').title() if anime_slug else 'Titre indisponible'
                logger.warning(f"⚠️ CATALOG - Pas de titre pour {anime_slug}, utilisation de '{anime_title}'")
            
            logger.debug(f"📺 CATALOG - Anime: {anime_slug} -> Titre: '{anime_title}'")
            
            genres_raw = anime.get('genres', '')
            genres = [g.strip() for g in genres_raw.split(',') if g.strip()] if genres_raw else []

            if genre and genre not in genres:
                continue

            genre_links = _build_genre_links(request, b64config, genres)

            meta = {
                "id": f"as:{anime.get('slug')}",
                "type": "anime",
                "name": anime_title,
                "poster": anime.get('image'),
                "posterShape": "poster",
                "background": anime.get('image'),
                "genres": genres,
                "imdbRating": None,
                "links": genre_links,
            }
            
            metas.append(meta)

        if search and genre:
            logger.info(f"🔍 CATALOG - Recherche '{search}' + Genre '{genre}': {len(metas)} animes trouvés")
        elif search:
            logger.info(f"🔍 CATALOG - Recherche '{search}': {len(metas)} animes trouvés")
        elif genre:
            logger.info(f"🎭 CATALOG - Genre '{genre}': {len(metas)} animes trouvés")
        else:
            logger.info(f"🔍 CATALOG - Retour de tous les {len(metas)} animes valides")

        return {"metas": metas}
        
    except Exception as e:
        logger.error(f"Erreur dans le catalogue: {e}")
        raise AnimeNotFoundException(f"Erreur catalogue: {str(e)}")


@main.get("/meta/anime/{id}.json")
@main.get("/{b64config}/meta/anime/{id}.json")
async def animesama_meta(request: Request, id: str, b64config: str = None, animesama_api: AnimeSamaAPI = Depends(get_animesama_api_dependency), animesama_player: AnimeSamaPlayer = Depends(get_animesama_player_dependency)):
    """Fournit les métadonnées détaillées d'un anime."""
    if not id.startswith("as:"):
        return {"meta": {}}

    anime_slug = id.replace("as:", "")

    anime_data = await get_or_fetch_anime_details(animesama_api.details, anime_slug)

    if not anime_data:
        return {"meta": {}}

    
    meta = {
        "id": f"as:{anime_data.get('slug')}",
        "type": "anime",
        "name": anime_data.get('title', anime_slug.replace('-', ' ').title()),
        "poster": anime_data.get('image'),
        "posterShape": "poster", 
        "background": anime_data.get('image'),
        "description": anime_data.get('synopsis', 'Aucune description disponible'),
        "genres": anime_data.get('genres', []) if isinstance(anime_data.get('genres'), list) else [],
        "imdbRating": None,
        "behaviorHints": {
            "hasScheduledVideos": True
        }
    }

    videos = []

    seasons = anime_data.get("seasons", [])
    
    async def detect_episodes_for_season(season):
        """Détecte le nombre d'épisodes pour une saison."""
        season_number = season.get('season_number')
        try:
            player = animesama_player
            episode_counts_dict = await player.get_available_episodes_count(anime_slug, season)
            
            available_episodes = max(episode_counts_dict.values()) if episode_counts_dict else 0
            
            if available_episodes > 0:
                return season_number, available_episodes
            else:
                if season_number == 998:
                    return season_number, 5
                elif season_number == 0:
                    return season_number, 6
                elif season_number == 999:
                    return season_number, 4
                else:
                    return season_number, 12
        except Exception as e:
            logger.warning(f"Impossible de détecter le nombre d'épisodes pour {anime_slug} S{season_number}: {e}")
            if season_number == 998:
                return season_number, 5
            elif season_number == 0:  # Spéciaux
                return season_number, 6 
            elif season_number == 999:  # Hors-série
                return season_number, 4
            else:  # Saisons normales
                return season_number, 12
    
    logger.info(f"🚀 Détection parallèle des épisodes pour {len(seasons)} saisons de {anime_slug}")
    detection_tasks = [detect_episodes_for_season(season) for season in seasons]
    episodes_results = await asyncio.gather(*detection_tasks)
    
    episodes_map = dict(episodes_results)
    
    for season in seasons:
        season_number = season.get('season_number')
        season_name = season.get('name')
        max_episodes = episodes_map.get(season_number, 12)  # Fallback à 12 si problème
        
        for episode_num in range(1, max_episodes + 1):
            if season_number == 998:
                logger.info(f"🎬 FILM DETECTE - anime: {anime_slug}, saison: {season_number}, episode: {episode_num}")
                try:
                    film_title = await animesama_api.get_film_title(anime_slug, episode_num)
                    logger.info(f"🎬 FILM - Fonction get_film_title appelée, résultat: '{film_title}'")
                    if film_title:
                        episode_title = film_title
                        episode_overview = film_title
                        logger.info(f"🎬 FILM - Titre final utilisé: '{episode_title}'")
                    else:
                        episode_title = f"Film {episode_num}"
                        episode_overview = f"Film {episode_num}"
                        logger.warning(f"🎬 FILM - Titre par défaut utilisé: '{episode_title}'")
                except Exception as e:
                    logger.error(f"🎬 FILM - Erreur récupération titre {anime_slug} #{episode_num}: {e}")
                    episode_title = f"Film {episode_num}"
                    episode_overview = f"Film {episode_num}"
            else:
                logger.debug(f"📺 EPISODE - anime: {anime_slug}, saison: {season_number}, episode: {episode_num}")
                episode_title = f"Episode {episode_num}"
                episode_overview = anime_data.get('synopsis', f"Episode {episode_num} de {season_name}")
            
            videos.append({
                "id": f"as:{anime_slug}:s{season_number}e{episode_num}",
                "title": episode_title,
                "season": season_number,
                "episode": episode_num,
                "thumbnail": anime_data.get('image'),
                "overview": episode_overview
            })
    
    meta['videos'] = videos

    # Add links
    genres = anime_data.get('genres', [])
    if isinstance(genres, str):
        genres = [g.strip() for g in genres.split(',') if g.strip()]
    meta['genres'] = genres
    
    genre_links = _build_genre_links(request, b64config, genres)
    meta['links'] = genre_links

    return {"meta": meta}