from typing import Optional, TypeVar, Type
from fastapi import Request, Depends

from astream.utils.http.client import HttpClient
from astream.scrapers.animesama.client import AnimeSamaAPI
from astream.scrapers.animesama.player import AnimeSamaPlayer
from astream.integrations.tmdb.service import TMDBService

T = TypeVar('T')

_global_http_client: Optional[HttpClient] = None


def set_global_http_client(client: HttpClient) -> None:
    """Définit instance globale HttpClient pour service layer."""
    global _global_http_client
    _global_http_client = client


def extract_client_ip(request: Request) -> str:
    """Extrait IP client en gérant proxies."""
    client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if not client_ip:
        client_ip = request.headers.get("X-Real-IP", "")
    if not client_ip:
        client_ip = getattr(request.client, "host", "unknown")
    return client_ip


def get_http_client(request: Request) -> HttpClient:
    """Dépendance pour obtenir instance partagée HttpClient."""
    return request.app.state.http_client


def _create_service_with_client_ip(service_class: Type[T], client: HttpClient, client_ip: Optional[str] = None) -> T:
    """Factory générique pour services avec IP client."""
    service = service_class(client)  # Instancier le service
    if client_ip and hasattr(service, 'set_client_ip'):  # Configurer l'IP si disponible
        service.set_client_ip(client_ip)
    return service


async def _get_service_async(service_class: Type[T], request: Optional[Request] = None) -> T:
    """Factory async générique pour services."""
    if request:
        client = request.app.state.http_client
        return _create_service_with_client_ip(service_class, client, extract_client_ip(request))
    else:
        if _global_http_client is None:
            raise RuntimeError("HttpClient global non configuré pour le service layer")
        return _create_service_with_client_ip(service_class, _global_http_client)


async def get_animesama_api(request: Optional[Request] = None) -> AnimeSamaAPI:
    """Dépendance AnimeSamaAPI avec HttpClient partagé et IP client."""
    return await _get_service_async(AnimeSamaAPI, request)


async def get_animesama_player(request: Optional[Request] = None) -> AnimeSamaPlayer:
    """Dépendance AnimeSamaPlayer avec HttpClient partagé et IP client."""
    return await _get_service_async(AnimeSamaPlayer, request)


def get_animesama_api_dependency(request: Request, client: HttpClient = Depends(get_http_client)) -> AnimeSamaAPI:
    """Dépendance FastAPI AnimeSamaAPI."""
    return _create_service_with_client_ip(AnimeSamaAPI, client, extract_client_ip(request))


def get_animesama_player_dependency(request: Request, client: HttpClient = Depends(get_http_client)) -> AnimeSamaPlayer:
    """Dépendance FastAPI AnimeSamaPlayer."""
    return _create_service_with_client_ip(AnimeSamaPlayer, client, extract_client_ip(request))


def get_global_http_client() -> HttpClient:
    """Récupère le client HTTP global."""
    if _global_http_client is None:
        raise RuntimeError("HttpClient global non configuré")
    return _global_http_client


def get_tmdb_service(request: Request, client: HttpClient = Depends(get_http_client)) -> TMDBService:
    """Dépendance FastAPI TMDBService."""
    return TMDBService(client)


async def get_tmdb_service_async(request: Optional[Request] = None) -> TMDBService:
    """Dépendance TMDBService avec HttpClient partagé."""
    return await _get_service_async(TMDBService, request)
