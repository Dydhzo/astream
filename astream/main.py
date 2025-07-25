import asyncio
import os
import signal
import sys
import threading
import time
from contextlib import asynccontextmanager, contextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from astream.api.core import main as core_router
from astream.api.stream import streams as stream_router
from astream.config.app_settings import settings
from astream.utils.database import (
    setup_database,
    teardown_database,
    cleanup_expired_locks,
)
from astream.utils.dependencies import set_global_http_client
from astream.utils.http_client import HttpClient
from astream.utils.logger import logger
from astream.utils.error_handler import global_exception_handler
from astream.utils.dataset_loader import DatasetLoader, set_dataset_loader


class LoguruMiddleware(BaseHTTPMiddleware):
    """Enregistre les requêtes HTTP avec Loguru."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = None
        status_code = 500
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as e:
            logger.log("ERROR", f"Exception durant le traitement de la requête: {e}")
            raise
        finally:
            process_time = time.time() - start_time
            if status_code >= 400:
                logger.log("API", f"{request.method} {request.url.path} [{status_code}] {process_time:.3f}s")
            else:
                logger.log("API", f"{request.method} {request.url.path} [{status_code}] {process_time:.3f}s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gère le cycle de vie de l'application FastAPI."""
    await setup_database()
    
    try:
        app.state.http_client = HttpClient()
        logger.log("ASTREAM", "Client HTTP initialisé")
        
        set_global_http_client(app.state.http_client)
        
        # Initialiser le dataset loader
        if settings.DATASET_ENABLED:
            dataset_loader = DatasetLoader(app.state.http_client)
            await dataset_loader.initialize()
            set_dataset_loader(dataset_loader)
            logger.log("ASTREAM", "Dataset loader initialisé")
        else:
            logger.log("ASTREAM", "Dataset désactivé")

        logger.log("ASTREAM", "Initialisation terminée - Prêt à scraper Anime-Sama")

    except Exception as e:
        logger.log("ERROR", f"Échec de l'initialisation : {e}")
        raise RuntimeError(f"L'initialisation a échoué : {e}")

    cleanup_task = asyncio.create_task(cleanup_expired_locks())

    try:
        yield
    finally:
        cleanup_task.cancel()

        try:
            await asyncio.gather(cleanup_task, return_exceptions=True)
        except asyncio.CancelledError:
            pass
        
        await app.state.http_client.close()
        await teardown_database()
        logger.log("ASTREAM", "Ressources nettoyées - Arrêt propre")


app = FastAPI(
    title=settings.ADDON_NAME,
    summary=f"{settings.ADDON_NAME} – Addon non officiel pour accéder au contenu d'Anime-Sama",
    lifespan=lifespan,
    redoc_url=None,
)

app.add_middleware(LoguruMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(Exception, global_exception_handler)

static_dir = "astream/templates"
if os.path.exists(static_dir) and os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
else:
    logger.log("WARNING", f"Répertoire statique manquant: {static_dir}")

app.include_router(core_router)
app.include_router(stream_router)


class Server(uvicorn.Server):
    """Serveur Uvicorn personnalisé pour démarrage en thread séparé."""
    def install_signal_handlers(self):
        pass

    @contextmanager
    def run_in_thread(self):
        thread = threading.Thread(target=self.run, name="AStream")
        thread.start()
        try:
            while not self.started:
                time.sleep(1e-3)
            yield
        except Exception as e:
            logger.log("ERROR", f"Erreur dans le thread du serveur: {e}")
            raise e
        finally:
            self.should_exit = True
            raise SystemExit(0)


def signal_handler(sig, frame):
    """Gestionnaire de signal pour arrêt propre du serveur."""
    logger.log("ASTREAM", "Arret en cours...")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def start_log():
    """Initialise les logs de démarrage de l'application."""
    """Affiche la configuration de démarrage."""
    logger.log(
        "ASTREAM",
        f"Serveur demarre sur http://{settings.FASTAPI_HOST}:{settings.FASTAPI_PORT} - {settings.FASTAPI_WORKERS} workers",
    )
    logger.log(
        "ASTREAM",
        f"Base de donnees ({settings.DATABASE_TYPE}): {settings.DATABASE_PATH if settings.DATABASE_TYPE == 'sqlite' else settings.DATABASE_URL} - TTL: anime_data={settings.EPISODE_PLAYERS_TTL}s",
    )
    logger.log("ASTREAM", f"HTML d'en-tete personnalise: {bool(settings.CUSTOM_HEADER_HTML)}")
    logger.log("ASTREAM", f"Dataset: {'Activé' if settings.DATASET_ENABLED else 'Désactivé'} - Auto-update: {'Activé' if settings.AUTO_UPDATE_DATASET else 'Désactivé'}")


def run_with_uvicorn():
    """Lance le serveur avec Uvicorn."""
    """Lance le serveur avec Uvicorn uniquement."""
    config = uvicorn.Config(
        app,
        host=settings.FASTAPI_HOST,
        port=settings.FASTAPI_PORT,
        proxy_headers=True,
        forwarded_allow_ips="*",
        workers=settings.FASTAPI_WORKERS,
        log_config=None,
    )
    server = Server(config=config)

    with server.run_in_thread():
        start_log()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.log("ASTREAM", "Arrêt manuel du serveur")
        except Exception as e:
            logger.log("ERROR", f"Erreur inattendue: {e}")
        finally:
            logger.log("ASTREAM", "Serveur arrêté")


def run_with_gunicorn():
    """Lance le serveur avec Gunicorn en mode multi-workers."""
    """Lance le serveur avec Gunicorn et workers Uvicorn."""
    import gunicorn.app.base

    class StandaloneApplication(gunicorn.app.base.BaseApplication):
        def __init__(self, app, options=None):
            self.options = options or {}
            self.application = app
            super().__init__()

        def load_config(self):
            config = {
                key: value
                for key, value in self.options.items()
                if key in self.cfg.settings and value is not None
            }
            for key, value in config.items():
                self.cfg.set(key.lower(), value)

        def load(self):
            return self.application

    workers = settings.FASTAPI_WORKERS
    if workers < 1:
        workers = min((os.cpu_count() or 1) * 2 + 1, 12)

    options = {
        "bind": f"{settings.FASTAPI_HOST}:{settings.FASTAPI_PORT}",
        "workers": workers,
        "worker_class": "uvicorn.workers.UvicornWorker",
        "timeout": 120,
        "keepalive": 5,
        "preload_app": True,
        "proxy_protocol": True,
        "forwarded_allow_ips": "*",
        "loglevel": "warning",
    }

    start_log()
    logger.log("ASTREAM", f"Démarrage Gunicorn avec {workers} workers")

    StandaloneApplication(app, options).run()


if __name__ == "__main__":
    if os.name == "nt" or not settings.USE_GUNICORN:
        run_with_uvicorn()
    else:
        run_with_gunicorn()