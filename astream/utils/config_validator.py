import orjson

from astream.utils.validators import ConfigModel, default_config
import base64
from astream.utils.logger import logger


def validate_config(b64config: str) -> dict:
    """Valide et traite configuration encodée base64."""
    try:
        # Décoder base64 URL-safe
        try:
            decoded_config = base64.urlsafe_b64decode(b64config).decode()
        except Exception:
            raise ValueError("Chaîne base64 invalide")
        config = orjson.loads(decoded_config)
        validated_config = ConfigModel(**config).model_dump()
        return validated_config
    except (ValueError, TypeError, KeyError) as e:
        logger.warning(f"⚠️ WARNING: Config utilisateur invalide: {e}. Retour config par défaut")
        return default_config
    except Exception as e:
        logger.error(f"❌ ERROR: Erreur validation configuration: {e}. Retour config par défaut")
        return default_config


def config_check(b64config: str):
    """Wrapper validation configuration."""
    return validate_config(b64config)
