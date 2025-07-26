import sys
import os

from loguru import logger
from astream.config.app_settings import settings


def setup_logger():
    """Configure le logger Loguru avec niveaux personnalisés et couleurs."""
    # Déterminer le niveau de log depuis les variables d'environnement ou config
    log_level = os.getenv("LOG_LEVEL")
    if not log_level:
        try:
            log_level = getattr(settings, 'LOG_LEVEL', 'DEBUG')
        except (ImportError, AttributeError):
            log_level = "DEBUG"
    
    # Définir niveaux personnalisés avec icônes
    logger.level("ASTREAM", no=50, icon="🚀", color="<fg #7871d6>")
    logger.level("ANIMESAMA", no=48, icon="🐍", color="<fg #4CAF50>")
    logger.level("API", no=45, icon="📡", color="<fg #2196F3>")
    logger.level("STREAM", no=42, icon="🎬", color="<fg #FF9800>")
    logger.level("DATABASE", no=40, icon="🔒", color="<fg #9C27B0>")
    logger.level("PROXY", no=37, icon="🌐", color="<fg #00BCD4>")
    logger.level("PERFORMANCE", no=35, icon="⚡", color="<fg #FFEB3B>")
    logger.level("DATASET", no=33, icon="📦", color="<fg #607D8B>")
    
    # Niveaux standards avec icônes
    logger.level("INFO", icon="💡", color="<fg #00BCD4>")
    logger.level("DEBUG", icon="🔍", color="<fg #795548>")
    logger.level("WARNING", icon="⚠️", color="<fg #FF5722>")
    logger.level("ERROR", icon="❌", color="<fg #F44336>")
    logger.level("SUCCESS", icon="✅", color="<fg #4CAF50>")

    # Configurer format selon le niveau
    if log_level == "PRODUCTION":
        log_format = "<white>{time:YYYY-MM-DD HH:mm:ss}</white> | <level>{level}</level> | <level>{message}</level>"
        actual_level = "WARNING"
    else:
        log_format = (
            "<white>{time:YYYY-MM-DD}</white> <magenta>{time:HH:mm:ss}</magenta> | "
            "<level>{level.icon}</level> <level>{level}</level> | "
            "<cyan>{module}</cyan>.<cyan>{function}</cyan> - <level>{message}</level>"
        )
        actual_level = "DEBUG"

    logger.remove()
    logger.add(
        sys.stderr,
        level=actual_level,
        format=log_format,
        backtrace=False,
        diagnose=False,
        enqueue=True,
    )


    if log_level == "PRODUCTION":
        logger.log("ASTREAM", f"MODE PRODUCTION - Logs essentiels uniquement")
    else:
        logger.log("ASTREAM", f"MODE DEBUG - Logs détaillés activés")

setup_logger()
