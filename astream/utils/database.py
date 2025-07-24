import os
import time
import json
import asyncio

from astream.utils.logger import logger
from astream.config.app_settings import database, settings

DATABASE_VERSION = "1.0"


async def setup_database():
    """Initialise la base de données et effectue les migrations."""
    try:
        if settings.DATABASE_TYPE == "sqlite":
            os.makedirs(os.path.dirname(settings.DATABASE_PATH), exist_ok=True)
            if not os.path.exists(settings.DATABASE_PATH):
                open(settings.DATABASE_PATH, "a").close()

        await database.connect()

        await database.execute("CREATE TABLE IF NOT EXISTS db_version (id INTEGER PRIMARY KEY CHECK (id = 1), version TEXT)")
        current_version = await database.fetch_val("SELECT version FROM db_version WHERE id = 1")

        if current_version != DATABASE_VERSION:
            logger.info(f"🔒 DATABASE: Migration v{current_version} → v{DATABASE_VERSION}")

            if settings.DATABASE_TYPE == "sqlite":
                allowed_tables = {'scrape_lock', 'metadata'}
                tables = await database.fetch_all("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('db_version', 'sqlite_sequence')")
                for table in tables:
                    table_name = table['name']
                    if table_name not in allowed_tables:
                        logger.warning(f"🔒 DATABASE: Table non autorisée ignorée: {table_name}")
                        continue
                    if not table_name.replace('_', '').isalnum() or len(table_name) > 64:
                        logger.warning(f"🔒 DATABASE: Table format nom invalide ignorée: {table_name}")
                        continue
                    # Sécurisation supplémentaire : double validation du nom de table
                    if table_name in allowed_tables and table_name.replace('_', '').isalnum():
                        await database.execute("DROP TABLE IF EXISTS " + table_name)
                        logger.info(f"🔒 DATABASE: Table supprimée: {table_name}")
                    else:
                        logger.error(f"🔒 DATABASE: Tentative suppression table non autorisée: {table_name}")
            else:
                await database.execute("""
                    DO $$ DECLARE r RECORD;
                    BEGIN
                        FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = current_schema() AND tablename != 'db_version') LOOP
                            EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                        END LOOP;
                    END $$;
                """)

            if settings.DATABASE_TYPE == "sqlite":
                await database.execute("INSERT OR REPLACE INTO db_version VALUES (1, :version)", {"version": DATABASE_VERSION})
            else:
                await database.execute("INSERT INTO db_version VALUES (1, :version) ON CONFLICT (id) DO UPDATE SET version = :version", {"version": DATABASE_VERSION})
            logger.info(f"🚀 ASTREAM: Migration base de données vers v{DATABASE_VERSION} terminée")

        await database.execute("CREATE TABLE IF NOT EXISTS scrape_lock (lock_key TEXT PRIMARY KEY, instance_id TEXT, timestamp INTEGER, expires_at INTEGER)")
        await database.execute("CREATE TABLE IF NOT EXISTS metadata (id TEXT PRIMARY KEY, data TEXT, timestamp REAL NOT NULL, expires_at REAL)")
        
        # Créer les index pour optimiser les performances
        await database.execute("CREATE INDEX IF NOT EXISTS idx_scrape_lock_key ON scrape_lock(lock_key)")
        await database.execute("CREATE INDEX IF NOT EXISTS idx_scrape_lock_expires ON scrape_lock(expires_at)")
        await database.execute("CREATE INDEX IF NOT EXISTS idx_metadata_id ON metadata(id)")
        await database.execute("CREATE INDEX IF NOT EXISTS idx_metadata_expires ON metadata(expires_at)")
        

        if settings.DATABASE_TYPE == "sqlite":
            await database.execute("PRAGMA busy_timeout=30000")
            await database.execute("PRAGMA journal_mode=WAL")
            await database.execute("PRAGMA synchronous=NORMAL")
            await database.execute("PRAGMA temp_store=MEMORY")
            await database.execute("PRAGMA cache_size=-2000")
            await database.execute("PRAGMA foreign_keys=ON")

        current_time = time.time()
        await database.execute("DELETE FROM metadata WHERE expires_at IS NOT NULL AND expires_at < :current_time;", {"current_time": current_time})

    except Exception as e:
        logger.error(f"🔒 DATABASE: Erreur configuration base de données: {e}")


async def cleanup_expired_locks():
    """Tâche de nettoyage périodique pour les verrous expirés."""
    while True:
        try:
            current_time = int(time.time())
            await database.execute("DELETE FROM scrape_lock WHERE expires_at < :current_time", {"current_time": current_time})
        except Exception as e:
            logger.error(f"🔒 DATABASE: Erreur nettoyage périodique verrous: {e}")
        await asyncio.sleep(60)


async def get_metadata_from_cache(cache_id: str):
    """Récupère les métadonnées depuis le cache."""
    current_time = time.time()
    query = "SELECT data FROM metadata WHERE id = :cache_id AND expires_at > :current_time"
    result = await database.fetch_one(query, {"cache_id": cache_id, "current_time": current_time})
    if not result or not result["data"]:
        return None
    try:
        return json.loads(result["data"])
    except json.JSONDecodeError:
        return None


async def set_metadata_to_cache(cache_id: str, data, ttl: int = None):
    """Stocke les métadonnées dans le cache avec TTL intelligent."""
    current_time = time.time()
    
    # TTL intelligent si pas spécifié
    if ttl is None:
        ttl = await _get_intelligent_ttl(cache_id)
    
    expires_at = current_time + ttl
    if settings.DATABASE_TYPE == "sqlite":
        query = "INSERT OR REPLACE INTO metadata (id, data, timestamp, expires_at) VALUES (:cache_id, :data, :timestamp, :expires_at)"
    else:
        query = "INSERT INTO metadata (id, data, timestamp, expires_at) VALUES (:cache_id, :data, :timestamp, :expires_at) ON CONFLICT (id) DO UPDATE SET data = :data, timestamp = :timestamp, expires_at = :expires_at"
    values = {"cache_id": cache_id, "data": json.dumps(data), "timestamp": current_time, "expires_at": expires_at}
    await database.execute(query, values)


async def _get_intelligent_ttl(cache_id: str) -> int:
    """
    Calcule le TTL intelligent basé sur le type de contenu et le planning.
    
    Args:
        cache_id: ID du cache (ex: "as:one-piece", "as:anime_planning", "as:homepage:content")
        
    Returns:
        TTL en secondes
    """
    try:
        # Planning lui-même
        if cache_id == "as:anime_planning":
            return settings.PLANNING_CACHE_TTL
        
        # URLs players d'épisodes (TTL fixe)
        if cache_id.startswith("as:") and ":players:" in cache_id:
            return settings.EPISODE_PLAYERS_TTL
        
        # Métadonnées d'anime individuels (TTL intelligent planning)
        if cache_id.startswith("as:") and not any(x in cache_id for x in ["catalog", "search", "genre", "homepage", "filter", "players", "streams"]):
            anime_slug = cache_id.replace("as:", "").split(":")[0]  # Ex: "as:one-piece:saison1" -> "one-piece"
            from astream.scrapers.animesama_planning import get_smart_cache_ttl
            return await get_smart_cache_ttl(anime_slug)
        
        # Catalogues, recherches, listes dynamiques
        if any(x in cache_id for x in ["catalog", "search", "genre", "homepage", "filter"]):
            return settings.DYNAMIC_LISTS_TTL
        
        # Autres données anime (fallback)
        if cache_id.startswith("as:"):
            return settings.EPISODE_PLAYERS_TTL
        
        # Données non-anime (par défaut)
        return settings.EPISODE_PLAYERS_TTL
        
    except Exception as e:
        logger.warning(f"⚡ PERFORMANCE: Erreur calcul TTL intelligent '{cache_id}': {e}")
        return settings.EPISODE_PLAYERS_TTL


async def acquire_lock(lock_key: str, instance_id: str, duration: int = None) -> bool:
    """Acquiert un verrou distribué pour la clé donnée."""
    try:
        current_time = int(time.time())
        lock_duration = duration if duration is not None else settings.SCRAPE_LOCK_TTL
        expires_at = current_time + lock_duration
        
        if settings.DATABASE_TYPE == "sqlite":
            query = "INSERT OR IGNORE INTO scrape_lock (lock_key, instance_id, timestamp, expires_at) VALUES (:lock_key, :instance_id, :timestamp, :expires_at)"
        else:
            query = "INSERT INTO scrape_lock (lock_key, instance_id, timestamp, expires_at) VALUES (:lock_key, :instance_id, :timestamp, :expires_at) ON CONFLICT (lock_key) DO NOTHING"
        await database.execute(query, {"lock_key": lock_key, "instance_id": instance_id, "timestamp": current_time, "expires_at": expires_at})
        
        existing_lock = await database.fetch_one("SELECT instance_id, expires_at FROM scrape_lock WHERE lock_key = :lock_key", {"lock_key": lock_key})
        
        if existing_lock:
            if existing_lock["expires_at"] < current_time:
                deleted = await database.execute("DELETE FROM scrape_lock WHERE lock_key = :lock_key AND expires_at < :current_time", {"lock_key": lock_key, "current_time": current_time})
                return await acquire_lock(lock_key, instance_id, duration) if deleted else False
            if existing_lock["instance_id"] == instance_id:
                logger.debug(f"🔒 DATABASE: Verrou acquis: {lock_key}")
                return True
            else:
                logger.debug(f"🔒 DATABASE: Verrou déjà détenu par autre instance: {lock_key}")
                return False
        
        logger.debug(f"🔒 DATABASE: Verrou acquis: {lock_key}")
        return True
    except Exception as e:
        logger.warning(f"🔒 DATABASE: Échec acquisition verrou {lock_key}: {e}")
        return False


async def release_lock(lock_key: str, instance_id: str) -> bool:
    """Libère un verrou distribué pour la clé donnée."""
    try:
        await database.execute("DELETE FROM scrape_lock WHERE lock_key = :lock_key AND instance_id = :instance_id", {"lock_key": lock_key, "instance_id": instance_id})
        logger.debug(f"🔒 DATABASE: Verrou libéré: {lock_key}")
        return True
    except Exception as e:
        logger.warning(f"🔒 DATABASE: Échec libération verrou {lock_key}: {e}")
        return False


class DistributedLock:
    """Gestionnaire de contexte pour le verrouillage distribué."""
    def __init__(self, lock_key: str, instance_id: str = None, duration: int = None):
        self.lock_key = lock_key
        self.instance_id = instance_id or f"astream_{int(time.time())}"
        self.duration = duration if duration is not None else settings.SCRAPE_LOCK_TTL
        self.acquired = False
    
    async def __aenter__(self):
        start_time = time.time()
        timeout = settings.SCRAPE_WAIT_TIMEOUT
        
        while time.time() - start_time < timeout:
            self.acquired = await acquire_lock(self.lock_key, self.instance_id, self.duration)
            if self.acquired:
                logger.debug(f"🔒 DATABASE: Verrou acquis {self.lock_key} après {time.time() - start_time:.2f}s")
                return self
            
            logger.debug(f"🔒 DATABASE: Attente verrou {self.lock_key}...")
            await asyncio.sleep(1)
            
        raise LockAcquisitionError(f"Impossible d'acquérir le verrou {self.lock_key} après {timeout}s")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.acquired:
            await release_lock(self.lock_key, self.instance_id)


class LockAcquisitionError(Exception):
    """Levée lorsqu'un verrou ne peut pas être acquis."""
    pass


async def teardown_database():
    """Ferme la connexion à la base de données."""
    try:
        await database.disconnect()
    except Exception as e:
        logger.error(f"🔒 DATABASE: Erreur fermeture base de données: {e}")
