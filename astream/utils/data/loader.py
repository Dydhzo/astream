import os
import json
import asyncio
from typing import List, Dict, Any, Optional
from astream.utils.logger import logger
from astream.utils.http.client import HttpClient
from astream.config.settings import settings


class DatasetLoader:
    """Gestionnaire du dataset d'URLs directes."""
    
    def __init__(self, http_client: HttpClient):
        self.http_client = http_client
        # Utiliser un chemin relatif qui fonctionne sur Windows et Linux
        self.dataset_path = os.path.join("data", "dataset.json")
        self.dataset = {"anime": []}
        self._anime_dict = {}  # Cache pour recherche O(1)
        
    async def initialize(self):
        """Initialise le dataset au démarrage."""
        try:
            # 1. Vérifier si dataset local existe
            if os.path.exists(self.dataset_path):
                logger.log("DATASET", f"Dataset local trouvé: {self.dataset_path}")
                self.dataset = self._load_local_dataset()
            else:
                # 2. Si pas de dataset local ET dataset activé
                if settings.DATASET_ENABLED:
                    logger.log("DATASET", "Aucun dataset local - Téléchargement depuis GitHub")
                    await self._download_and_save_dataset()
                else:
                    logger.log("DATASET", "Dataset désactivé - Utilisation dataset vide")
                    self.dataset = {"anime": []}
            
            # 3. Construire le cache de recherche
            self._build_search_cache()
            
            # 4. Démarrer mise à jour en arrière-plan si activée
            if settings.DATASET_ENABLED and settings.DATASET_UPDATE_INTERVAL > 0:
                asyncio.create_task(self._periodic_update())
                
            logger.log("DATASET", f"Initialisé avec {len(self.dataset.get('anime', []))} anime")
            
        except Exception as e:
            logger.error(f"DATASET: Erreur initialisation: {e}")
            self.dataset = {"anime": []}
            self._anime_dict = {}
    
    def _load_local_dataset(self) -> Dict[str, Any]:
        """Charge le dataset depuis le fichier local."""
        try:
            with open(self.dataset_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.debug(f"DATASET: Dataset local chargé - {len(data.get('anime', []))} anime")
                return data
        except Exception as e:
            logger.warning(f"DATASET: Erreur lecture dataset local: {e}")
            return {"anime": []}
    
    async def _download_and_save_dataset(self):
        """Télécharge et sauvegarde le dataset depuis GitHub."""
        try:
            if not settings.DATASET_URL:
                logger.warning("DATASET: DATASET_URL non configurée")
                return
                
            logger.log("DATASET", f"Téléchargement depuis: {settings.DATASET_URL}")
            response = await self.http_client.get(settings.DATASET_URL)
            response.raise_for_status()
            
            remote_dataset = response.json()
            
            # Créer le dossier /data si nécessaire
            os.makedirs(os.path.dirname(self.dataset_path), exist_ok=True)
            
            # Sauvegarder localement
            with open(self.dataset_path, 'w', encoding='utf-8') as f:
                json.dump(remote_dataset, f, ensure_ascii=False, indent=2)
                
            self.dataset = remote_dataset
            logger.log("SUCCESS", f"Dataset téléchargé et sauvé - {len(self.dataset.get('anime', []))} anime")
            
        except Exception as e:
            logger.error(f"DATASET: Erreur téléchargement: {e}")
            self.dataset = {"anime": []}
    
    def _build_search_cache(self):
        """Construit le cache de recherche pour performance O(1)."""
        self._anime_dict = {}
        
        for anime in self.dataset.get("anime", []):
            anime_slug = anime.get("slug")
            if anime_slug:
                if anime_slug not in self._anime_dict:
                    self._anime_dict[anime_slug] = {"streams": []}
                
                # Format avec URLs groupées
                for stream in anime.get("streams", []):
                    season = stream.get("season")
                    episode = stream.get("episode") 
                    language = stream.get("language")
                    urls = stream.get("urls", [])
                        
                    if all([season is not None, episode is not None, language]):
                        for url in urls:
                            if url:
                                self._anime_dict[anime_slug]["streams"].append({
                                    "season": season,
                                    "episode": episode,
                                    "language": language,
                                    "url": url
                                })
        
        logger.debug(f"DATASET: Cache construit pour {len(self._anime_dict)} anime")
    
    async def get_streams(self, anime_slug: str, season: int, episode: int, language_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Récupère les streams depuis le dataset pour un épisode donné."""
        try:
            if not self.dataset.get("anime") or anime_slug not in self._anime_dict:
                return []
            
            anime_data = self._anime_dict[anime_slug]
            matching_streams = []
            
            for stream in anime_data["streams"]:
                if stream["season"] == season and stream["episode"] == episode:
                    # Filtrer par langue si demandé
                    if language_filter and language_filter != "Tout":
                        if language_filter == "VOSTFR" and stream["language"] != "VOSTFR":
                            continue
                        elif language_filter == "VF" and stream["language"] not in ["VF", "VF1", "VF2"]:
                            continue
                    
                    # Format compatible avec le reste du code
                    matching_streams.append({
                        "url": stream["url"],
                        "language": stream["language"]
                    })
            
            if matching_streams:
                logger.debug(f"DATASET: {len(matching_streams)} streams trouvés pour {anime_slug} S{season}E{episode}")
            
            return matching_streams
            
        except Exception as e:
            logger.error(f"DATASET: Erreur récupération streams {anime_slug}: {e}")
            return []
    
    async def _periodic_update(self):
        """Mise à jour périodique du dataset."""
        while True:
            try:
                # Vérifier que l'intervalle est valide (>0)
                if settings.DATASET_UPDATE_INTERVAL <= 0:
                    logger.log("DATASET", "Mise à jour périodique désactivée (intervalle <= 0)")
                    break
                    
                await asyncio.sleep(settings.DATASET_UPDATE_INTERVAL)
                
                if not settings.DATASET_URL:
                    continue
                    
                logger.debug("🔄 DATASET: Vérification mise à jour")
                
                # Télécharger et appliquer nouvelle version
                response = await self.http_client.get(settings.DATASET_URL)
                response.raise_for_status()
                remote_dataset = response.json()
                
                # Sauvegarder nouvelle version
                with open(self.dataset_path, 'w', encoding='utf-8') as f:
                    json.dump(remote_dataset, f, ensure_ascii=False, indent=2)
                
                self.dataset = remote_dataset
                self._build_search_cache()
                
                logger.log("SUCCESS", f"Dataset mis à jour - {len(self.dataset.get('anime', []))} anime")
                    
            except Exception as e:
                logger.warning(f"DATASET: Erreur mise à jour périodique: {e}")
    
    def reload_dataset(self):
        """Recharge le dataset depuis le fichier local (pour les scripts)."""
        try:
            self.dataset = self._load_local_dataset()
            self._build_search_cache()
            logger.log("SUCCESS", f"Dataset rechargé - {len(self.dataset.get('anime', []))} anime")
        except Exception as e:
            logger.error(f"DATASET: Erreur rechargement: {e}")


# Instance globale
_dataset_loader: Optional[DatasetLoader] = None


def get_dataset_loader() -> Optional[DatasetLoader]:
    """Récupère l'instance globale du dataset loader."""
    return _dataset_loader


def set_dataset_loader(loader: DatasetLoader):
    """Définit l'instance globale du dataset loader."""
    global _dataset_loader
    _dataset_loader = loader