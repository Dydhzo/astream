from typing import Dict, Any
from astream.config.settings import settings


def format_stream_for_stremio(video_url: str, language: str, anime_slug: str, season: int, source_prefix: str = "") -> Dict[str, Any]:
    """Formate un stream au format attendu par Stremio."""
    return {
        "name": f"🐍 {settings.ADDON_NAME}{source_prefix}",  # Nom affiché dans Stremio
        "title": f"🔗 {video_url}\n🌍 {language.upper()}",  # Informations détaillées
        "url": video_url,  # URL de streaming directe
        "language": language,  # Langue du contenu
        "behaviorHints": {
            "notWebReady": True,  # Pas de lecture web directe
            "bingeGroup": f"astream-{anime_slug}-{season}"  # Groupement pour binge-watching
        }
    }