from typing import Dict, Any, Optional
from enum import Enum

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from astream.utils.logger import logger


class ErrorCode(Enum):
    """Codes d'erreur standardisés."""
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    
    ANIME_NOT_FOUND = "ANIME_NOT_FOUND"
    SEASON_NOT_FOUND = "SEASON_NOT_FOUND" 
    EPISODE_NOT_FOUND = "EPISODE_NOT_FOUND"
    NO_STREAMS_AVAILABLE = "NO_STREAMS_AVAILABLE"
    
    SCRAPING_FAILED = "SCRAPING_FAILED"
    NETWORK_ERROR = "NETWORK_ERROR"
    PARSING_ERROR = "PARSING_ERROR"
    
    CACHE_ERROR = "CACHE_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    LOCK_ACQUISITION_FAILED = "LOCK_ACQUISITION_FAILED"


class AStreamException(Exception):
    """Exception de base pour AStream."""
    
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.INTERNAL_ERROR, 
                 details: Optional[Dict[str, Any]] = None, http_status: int = 500):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.http_status = http_status


class AnimeNotFoundException(AStreamException):
    """Anime non trouvé."""
    
    def __init__(self, anime_id: str):
        super().__init__(
            f"Anime non trouvé: {anime_id}",
            ErrorCode.ANIME_NOT_FOUND,
            {"anime_id": anime_id},
            404
        )


class NoStreamsAvailableException(AStreamException):
    """Aucun stream disponible."""
    
    def __init__(self, episode_id: str):
        super().__init__(
            f"Aucun stream disponible pour {episode_id}",
            ErrorCode.NO_STREAMS_AVAILABLE,
            {"episode_id": episode_id},
            404
        )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler global pour toutes les exceptions."""
    try:
        if isinstance(exc, AStreamException):
            logger.warning(f"⚠️ WARNING: Exception AStream: {exc.error_code.value} - {exc.message}")
            return JSONResponse(
                status_code=exc.http_status,
                content={
                    "error": exc.error_code.value,
                    "message": exc.message,
                    "details": exc.details
                }
            )
        
        elif isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": "HTTP_ERROR",
                    "message": str(exc.detail)
                }
            )
        
        else:
            logger.error(f"❌ ERROR: Exception non gérée: {str(exc)}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "INTERNAL_ERROR",
                    "message": "Une erreur interne s'est produite"
                }
            )
            
    except Exception as handler_error:
        logger.error(f"❌ ERROR: Erreur dans le handler d'exception: {handler_error}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "HANDLER_ERROR",
                "message": "Erreur critique du système"
            }
        )