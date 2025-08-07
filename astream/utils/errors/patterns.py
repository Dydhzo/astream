from functools import wraps
from typing import Any, Optional, Union, List, Dict
from astream.utils.logger import logger


def handle_common_errors(error_message_prefix: str = "Erreur", default_return: Any = None, log_level: str = "ERROR"):
    """Décorateur pour gestion standardisée des erreurs courantes."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.log(log_level, f"{error_message_prefix} dans {func.__name__}: {e}")
                return default_return
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.log(log_level, f"{error_message_prefix} dans {func.__name__}: {e}")
                return default_return
        
        # Déterminer si la fonction est async ou sync
        import asyncio  # Import local pour éviter les dépendances circulaires
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def safe_get_list(data: Dict, key: str, default: Optional[List] = None) -> List:
    """Récupération sécurisée de listes depuis dictionnaire."""
    if default is None:
        default = []
    return data.get(key, default) if isinstance(data.get(key), list) else default


def safe_get_dict(data: Dict, key: str, default: Optional[Dict] = None) -> Dict:
    """Récupération sécurisée de dictionnaires."""
    if default is None:
        default = {}
    return data.get(key, default) if isinstance(data.get(key), dict) else default


def safe_get_str(data: Dict, key: str, default: str = "") -> str:
    """Récupération sécurisée de strings."""
    value = data.get(key, default)
    return str(value) if value is not None else default


def safe_get_int(data: Dict, key: str, default: int = 0) -> int:
    """Récupération sécurisée d'entiers."""
    try:
        value = data.get(key, default)
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default