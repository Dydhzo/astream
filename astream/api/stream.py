import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from astream.scrapers.animesama import AnimeSamaAPI
from astream.scrapers.animesama_player import AnimeSamaPlayer
from astream.scrapers.animesama_details import get_or_fetch_anime_details
from astream.utils.logger import logger
from astream.utils.dependencies import get_animesama_api_dependency, get_animesama_player_dependency
from astream.utils.config_validator import config_check

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
            logger.debug(f"Parse episode_id: {episode_id} -> {anime_slug} (métadonnées)")
            return anime_slug, None, episode_id
        elif len(parts) == 3:
            # Format: as:anime_slug:s1e1 (streams)
            anime_slug, episode_id = parts[1], parts[2]
            logger.debug(f"Parse episode_id: {episode_id} -> {anime_slug}:{episode_id}")
            return anime_slug, episode_id, episode_id
        else:
            logger.error(f"Format episode_id invalide: '{episode_id}'")
            return None, None, None
    except (IndexError, ValueError) as e:
        logger.error(f"Erreur parsing episode_id '{episode_id}': {e}")
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
        logger.error(f"Erreur lors de l'extraction des infos d'épisode: {e}")
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
    logger.info(f"🎬 STREAM - Demande de flux pour: {episode_id}")
    
    # Vérifier config
    config = config_check(b64config)
    if not config:
        logger.warning("Configuration invalide ou manquante")
        return {"streams": []}
    
    # Parser episode_id
    anime_slug, episode_info, _ = await _parse_media_id(episode_id)
    if not anime_slug:
        return {"streams": []}
    
    # Pas d'episode_info = métadonnées, pas stream
    if not episode_info:
        logger.warning(f"Pas d'episode_info dans {episode_id}, retour de streams vides")
        return {"streams": []}
    
    # Extraire infos saison et épisode
    season_num, episode_num = await _extract_episode_info(episode_info)
    if season_num is None or episode_num is None:
        logger.warning(f"Impossible d'extraire les infos d'épisode de: {episode_info}")
        return {"streams": []}
    
    try:
        # Récupérer données anime avec saisons
        anime_data = await get_or_fetch_anime_details(animesama_api.details, anime_slug)
        if not anime_data:
            logger.warning(f"Aucune donnée trouvée pour l'anime: {anime_slug}")
            return {"streams": []}
        
        # Trouver saison correspondante
        seasons = anime_data.get("seasons", [])
        target_season = None
        
        for season in seasons:
            if season.get("season_number") == season_num:
                target_season = season
                break
        
        if not target_season:
            logger.warning(f"Saison {season_num} introuvable pour {anime_slug}")
            return {"streams": []}
        
        # Utiliser AnimeSamaPlayer pour extraire URLs
        player = animesama_player
        
        # Filtrer selon config langue
        language_filter = config.get("language", "Tout")
        
        # Extraire streams avec AnimeSamaPlayer
        streams = await player.get_episode_streams(
            anime_slug=anime_slug,
            season_data=target_season, 
            episode_number=episode_num,
            language_filter=language_filter,
            config=config
        )
        
        # Si aucun stream, retourner liste vide
        if not streams:
            logger.warning(f"AnimeSamaPlayer n'a trouvé aucun stream pour {anime_slug} S{season_num}E{episode_num}")
            streams = []
        
        logger.info(f"✅ STREAM - {len(streams)} flux trouvés pour {episode_id}")
        return {"streams": streams}
        
    except Exception as e:
        logger.error(f"❌ STREAM - Erreur lors de la récupération des flux: {e}")
        return {"streams": []}
