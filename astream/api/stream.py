import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from astream.scrapers.animesama import AnimeSamaAPI
from astream.scrapers.animesama_player import AnimeSamaPlayer
from astream.scrapers.animesama_details import get_or_fetch_anime_details
from astream.utils.logger import logger
from astream.utils.dependencies import get_animesama_api_dependency, get_animesama_player_dependency
from astream.utils.config_validator import validate_config
from astream.utils.animesama_service import AnimeSamaService

streams = APIRouter()


async def _parse_media_id(episode_id: str):
    """Analyse et valide le format de l'episode_id."""
    if "as:" not in episode_id:
        return None, None, None
    try:
        parts = episode_id.split(":")
        if len(parts) == 2:
            # Format: as:anime_slug (métadonnées)
            anime_slug = parts[1]
            logger.log("DEBUG", f"Parse episode_id: {episode_id} -> {anime_slug} (métadonnées)")
            return anime_slug, None, episode_id
        elif len(parts) == 3:
            # Format: as:anime_slug:s1e1 (streams)
            anime_slug, episode_id = parts[1], parts[2]
            logger.log("DEBUG", f"Parse episode_id: {episode_id} -> {anime_slug}:{episode_id}")
            return anime_slug, episode_id, episode_id
        else:
            logger.log("ERROR", f"Format episode_id invalide: '{episode_id}'")
            return None, None, None
    except (IndexError, ValueError) as e:
        logger.log("ERROR", f"Erreur parsing episode_id '{episode_id}': {e}")
        return None, None, None


async def _extract_episode_info(episode_id: str):
    """Extrait informations saison et épisode depuis ID."""
    try:
        # Format: s{season}e{episode}
        match = re.match(r's(\d+)e(\d+)', episode_id)
        if match:
            season_num = int(match.group(1))
            episode_num = int(match.group(2))
            return season_num, episode_num
        return None, None
    except Exception as e:
        logger.log("ERROR", f"Erreur lors de l'extraction des infos d'épisode: {e}")
        return None, None


@streams.get("/stream/anime/{episode_id}.json")
@streams.get("/{b64config}/stream/anime/{episode_id}.json")
async def get_anime_stream(
    request: Request, 
    episode_id: str, 
    b64config: str = None, 
    animesama_api: AnimeSamaAPI = Depends(get_animesama_api_dependency),
    animesama_player: AnimeSamaPlayer = Depends(get_animesama_player_dependency)
):
    """Endpoint principal pour récupérer les flux de streaming."""
    logger.log("STREAM", f"Demande de flux pour: {episode_id}")
    
    # Vérifier config
    config = validate_config(b64config)
    if not config:
        logger.log("WARNING", "Configuration invalide ou manquante")
        return {"streams": []}
    
    # Parser episode_id
    anime_slug, episode_info, _ = await _parse_media_id(episode_id)
    if not anime_slug:
        return {"streams": []}
    
    # Pas d'episode_info = métadonnées, pas stream
    if not episode_info:
        logger.log("WARNING", f"Pas d'episode_info dans {episode_id}, retour de streams vides")
        return {"streams": []}
    
    # Extraire infos saison et épisode
    season_num, episode_num = await _extract_episode_info(episode_info)
    if season_num is None or episode_num is None:
        logger.log("WARNING", f"Impossible d'extraire les infos d'épisode de: {episode_info}")
        return {"streams": []}
    
    try:
        # Récupérer données anime avec saisons
        anime_data = await get_or_fetch_anime_details(animesama_api.details, anime_slug)
        if not anime_data:
            logger.log("WARNING", f"Aucune donnée trouvée pour l'anime: {anime_slug}")
            return {"streams": []}
        
        # Trouver saison correspondante
        seasons = anime_data.get("seasons", [])
        target_season = None
        
        for season in seasons:
            if season.get("season_number") == season_num:
                target_season = season
                break
        
        if not target_season:
            logger.log("WARNING", f"Saison {season_num} introuvable pour {anime_slug}")
            return {"streams": []}
        
        # Utiliser AnimeSamaService pour combiner dataset + scraping
        service = AnimeSamaService()
        
        # Obtenir l'IP client pour le rate limiting
        client_ip = request.client.host if request.client else None
        
        # Filtrer selon config langue
        language_filter = config.get("language", "Tout")
        language_order = config.get("languageOrder", "VOSTFR,VF")
        
        # Construire l'episode_id au format attendu par le service
        formatted_episode_id = f"as:{anime_slug}:s{season_num}e{episode_num}"
        
        # Extraire streams avec AnimeSamaService (dataset + scraping)
        streams = await service.get_episode_streams(
            episode_id=formatted_episode_id,
            language_filter=language_filter,
            language_order=language_order,
            client_ip=client_ip
        )
        
        # Si aucun stream, retourner liste vide
        if not streams:
            logger.log("WARNING", f"AnimeSamaService n'a trouvé aucun stream pour {anime_slug} S{season_num}E{episode_num}")
            streams = []
        
        logger.log("STREAM", f"{len(streams)} flux trouvés pour {episode_id}")
        return {"streams": streams}
        
    except Exception as e:
        logger.log("ERROR", f"Erreur lors de la récupération des flux: {e}")
        return {"streams": []}
