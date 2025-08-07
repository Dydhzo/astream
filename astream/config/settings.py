from typing import Optional
from databases import Database
from pydantic_settings import BaseSettings, SettingsConfigDict
import sys


class AppSettings(BaseSettings):
    """Paramètres de l'application chargés depuis les variables d'environnement."""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ANIMESAMA_URL: Optional[str] = None
    ADDON_ID: Optional[str] = "community.astream"
    ADDON_NAME: Optional[str] = "AStream"
    FASTAPI_HOST: Optional[str] = "0.0.0.0"
    FASTAPI_PORT: Optional[int] = 8000
    FASTAPI_WORKERS: Optional[int] = 1
    USE_GUNICORN: Optional[bool] = True
    DATABASE_TYPE: Optional[str] = "sqlite"
    DATABASE_URL: Optional[str] = "username:password@hostname:port"
    DATABASE_PATH: Optional[str] = "data/astream.db"
    DATASET_ENABLED: Optional[bool] = True
    DATASET_URL: Optional[str] = None
    DATASET_UPDATE_INTERVAL: Optional[int] = 3600
    EPISODE_TTL: Optional[int] = 3600
    DYNAMIC_LIST_TTL: Optional[int] = 3600
    PLANNING_TTL: Optional[int] = 3600
    ONGOING_ANIME_TTL: Optional[int] = 3600
    FINISHED_ANIME_TTL: Optional[int] = 604800
    SCRAPE_LOCK_TTL: Optional[int] = 300
    SCRAPE_WAIT_TIMEOUT: Optional[int] = 30
    RATE_LIMIT_PER_USER: Optional[float] = 1
    HTTP_TIMEOUT: Optional[int] = 15
    PROXY_URL: Optional[str] = None
    PROXY_BYPASS_DOMAINS: Optional[str] = ""
    EXCLUDED_DOMAINS: Optional[str] = ""
    CUSTOM_HEADER_HTML: Optional[str] = None
    LOG_LEVEL: Optional[str] = "DEBUG"
    TMDB_API_KEY: Optional[str] = None
    TMDB_TTL: Optional[int] = 604800

# Instance globale des paramètres
settings = AppSettings()

# Vérification obligatoire de l'URL AnimeSama
if not settings.ANIMESAMA_URL:
    print("ERREUR: ANIMESAMA_URL non configurée. Consultez le README : https://github.com/Dydhzo/astream#configuration")
    sys.exit(1)

# Normalisation de l'URL (suppression du slash final)
if settings.ANIMESAMA_URL.endswith('/'):
    settings.ANIMESAMA_URL = settings.ANIMESAMA_URL.rstrip('/')  # Supprimer le slash final

if not settings.ANIMESAMA_URL.startswith(('http://', 'https://')):
    settings.ANIMESAMA_URL = f"https://{settings.ANIMESAMA_URL}"

web_config = {
    "languages": {
        "Tout": "Tout afficher",
        "VOSTFR": "VOSTFR uniquement",
        "VF": "VF uniquement"
    },
    "tmdb": {
        "enabled": bool(settings.TMDB_API_KEY),
        "episode_mapping": False
    }
}

database_url = f"sqlite:///{settings.DATABASE_PATH}" if settings.DATABASE_TYPE == "sqlite" else settings.DATABASE_URL
database = Database(database_url)