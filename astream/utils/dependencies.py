from typing import Optional
from fastapi import Request, Depends

from astream.utils.http_client import HttpClient
from astream.scrapers.animesama import AnimeSamaAPI
from astream.scrapers.animesama_player import AnimeSamaPlayer

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


def _create_animesama_api(client: HttpClient, client_ip: Optional[str] = None) -> AnimeSamaAPI:
    """Crée instance AnimeSamaAPI."""
    api = AnimeSamaAPI(client)
    if client_ip:
        api.set_client_ip(client_ip)
    return api


async def get_animesama_api(request: Optional[Request] = None) -> AnimeSamaAPI:
    """Dépendance AnimeSamaAPI avec HttpClient partagé et IP client."""
    if request:
        client = request.app.state.http_client
        return _create_animesama_api(client, extract_client_ip(request))
    else:
        if _global_http_client is None:
            raise RuntimeError("HttpClient global non configuré pour le service layer")
        return _create_animesama_api(_global_http_client)


def _create_animesama_player(client: HttpClient, client_ip: Optional[str] = None) -> AnimeSamaPlayer:
    """Crée instance AnimeSamaPlayer."""
    player = AnimeSamaPlayer(client)
    if client_ip:
        player.set_client_ip(client_ip)
    return player


async def get_animesama_player(request: Optional[Request] = None) -> AnimeSamaPlayer:
    """Dépendance AnimeSamaPlayer avec HttpClient partagé et IP client."""
    if request:
        client = request.app.state.http_client
        return _create_animesama_player(client, extract_client_ip(request))
    else:
        if _global_http_client is None:
            raise RuntimeError("HttpClient global non configuré pour le service layer")
        return _create_animesama_player(_global_http_client)


def get_animesama_api_dependency(request: Request, client: HttpClient = Depends(get_http_client)) -> AnimeSamaAPI:
    """Dépendance FastAPI AnimeSamaAPI."""
    return _create_animesama_api(client, extract_client_ip(request))


def get_animesama_player_dependency(request: Request, client: HttpClient = Depends(get_http_client)) -> AnimeSamaPlayer:
    """Dépendance FastAPI AnimeSamaPlayer."""
    return _create_animesama_player(client, extract_client_ip(request))
