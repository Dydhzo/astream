from fastapi import APIRouter, Depends, Request

from astream.scrapers.animesama.client import AnimeSamaAPI
from astream.scrapers.animesama.player import AnimeSamaPlayer
from astream.scrapers.animesama.details import get_or_fetch_anime_details
from astream.utils.logger import logger
from astream.utils.dependencies import get_animesama_api_dependency, get_animesama_player_dependency
from astream.utils.validation.helpers import validate_config
from astream.utils.parsers import MediaIdParser
from astream.services.anime import AnimeSamaService

# Router pour les endpoints de streaming
streams = APIRouter()


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
    
    # Vérifier config utilisateur
    config = validate_config(b64config)  # Décoder config base64
    if not config:
        logger.warning("Configuration invalide ou manquante")
        return {"streams": []}
    
    # Parser episode_id
    parsed = MediaIdParser.parse_episode_id(episode_id)
    if not parsed or parsed['is_metadata_only']:
        logger.warning(f"Episode_id invalide ou métadonnées seulement: {episode_id}")
        return {"streams": []}
    
    anime_slug = parsed['anime_slug']
    season_num = parsed['season_number']
    episode_num = parsed['episode_number']
    
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
        
        # Utiliser AnimeSamaService pour combiner dataset + scraping
        service = AnimeSamaService()
        
        # Obtenir l'IP client pour le rate limiting
        client_ip = request.client.host if request.client else None
        
        # Filtrer selon config langue
        language_filter = config.get("language", "Tout")
        language_order = config.get("languageOrder", "VOSTFR,VF")
        
        # Construire l'episode_id au format attendu par le service
        formatted_episode_id = MediaIdParser.format_episode_id(anime_slug, season_num, episode_num)
        
        # Extraire streams avec AnimeSamaService (dataset + scraping)
        streams = await service.get_episode_streams(
            episode_id=formatted_episode_id,
            language_filter=language_filter,
            language_order=language_order,
            client_ip=client_ip,
            config=config
        )
        
        # Si aucun stream, retourner liste vide
        if not streams:
            logger.warning(f"AnimeSamaService n'a trouvé aucun stream pour {anime_slug} S{season_num}E{episode_num}")
            streams = []
        
        logger.log("STREAM", f"{len(streams)} flux trouvés pour {episode_id}")
        return {"streams": streams}
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des flux: {e}")
        return {"streams": []}
