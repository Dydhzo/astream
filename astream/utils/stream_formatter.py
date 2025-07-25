from typing import Dict, Any
from astream.config.app_settings import settings


def format_stream_for_stremio(video_url: str, language: str, anime_slug: str, season: int, source_prefix: str = "") -> Dict[str, Any]:
    """Formate un stream au format attendu par Stremio."""
    return {
        "name": f"🐍 {settings.ADDON_NAME}{source_prefix}",
        "title": f"🔗 {video_url}\n🌍 {language.upper()}",
        "url": video_url,
        "language": language,  # Conserver la langue pour le tri
        "behaviorHints": {
            "notWebReady": True,
            "bingeGroup": f"astream-{anime_slug}-{season}"
        }
    }