from typing import Optional
from databases import Database
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Paramètres de l'application chargés depuis les variables d'environnement."""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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
    DATASET_URL: Optional[str] = "https://raw.githubusercontent.com/Dydhzo/astream/main/dataset.json"
    AUTO_UPDATE_DATASET: Optional[bool] = True
    DATASET_UPDATE_INTERVAL: Optional[int] = 3600
    EPISODE_PLAYERS_TTL: Optional[int] = 3600
    DYNAMIC_LISTS_TTL: Optional[int] = 3600
    PLANNING_CACHE_TTL: Optional[int] = 3600
    ONGOING_ANIME_TTL: Optional[int] = 3600
    FINISHED_ANIME_TTL: Optional[int] = 604800
    SCRAPE_LOCK_TTL: Optional[int] = 300
    SCRAPE_WAIT_TIMEOUT: Optional[int] = 30
    RATE_LIMIT_PER_USER: Optional[float] = 1
    HTTP_TIMEOUT: Optional[int] = 15
    PROXY_URL: Optional[str] = None
    PROXY_BYPASS_DOMAINS: Optional[str] = ""
    ANIMESAMA_URL: Optional[str] = "https://anime-sama.fr"
    EXCLUDED_DOMAIN: Optional[str] = ""
    CUSTOM_HEADER_HTML: Optional[str] = None
    LOG_LEVEL: Optional[str] = "DEBUG"


settings = AppSettings()

web_config = {
    "languages": {
        "Tout": "Tout afficher",
        "VOSTFR": "VOSTFR uniquement",
        "VF": "VF uniquement"
    }
}

database_url = f"sqlite:///{settings.DATABASE_PATH}" if settings.DATABASE_TYPE == "sqlite" else settings.DATABASE_URL
database = Database(database_url)