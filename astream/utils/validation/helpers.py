import orjson

from astream.utils.validation.models import ConfigModel, default_config
import base64
from astream.utils.logger import logger


def validate_config(b64config: str) -> dict:
    """Valide et traite configuration encodée base64."""
    try:
        # Décoder base64 URL-safe
        try:
            decoded_config = base64.urlsafe_b64decode(b64config).decode()  # Décodage
        except Exception:
            raise ValueError("Chaîne base64 invalide")  # Erreur format
        config = orjson.loads(decoded_config)  # Parse JSON
        validated_config = ConfigModel(**config).model_dump()  # Validation
        return validated_config
    except (ValueError, TypeError, KeyError) as e:
        logger.warning(f"Config utilisateur invalide: {e}. Retour config par défaut")
        return default_config
    except Exception as e:
        logger.error(f"Erreur validation configuration: {e}. Retour config par défaut")
        return default_config
