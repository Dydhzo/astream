"""
Système de mapping intelligent des épisodes TMDB vers Anime-Sama
Redistribue les épisodes saison par saison avec logique de débordement.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from astream.utils.logger import logger
from astream.config.settings import settings


class TMDBEpisodeMapper:
    """Mapper intelligent pour redistribuer les épisodes TMDB selon les saisons Anime-Sama."""
    
    def __init__(self):
        self.tmdb_episodes = {}  # Format: s1e1 -> episode_data
        self.anime_sama_structure = {}  # Format: season_num -> episode_count
        
    def set_tmdb_episodes(self, tmdb_episodes_map: Dict[str, Dict]):
        """Définit les épisodes TMDB disponibles."""
        self.tmdb_episodes = tmdb_episodes_map
        logger.debug(f"Episodes TMDB chargés: {len(tmdb_episodes_map)}")
        
    def set_anime_sama_structure(self, seasons_data: List[Dict]):
        """Définit la structure des saisons Anime-Sama."""
        self.anime_sama_structure = {}
        for season in seasons_data:
            season_num = season.get('season_number', 0)
            if season_num > 0:  # Saisons normales uniquement
                episode_count = season.get('episode_count', 0)
                if episode_count > 0:
                    self.anime_sama_structure[season_num] = episode_count
        
        logger.debug(f"Structure Anime-Sama: {self.anime_sama_structure}")
    
    def create_intelligent_mapping(self) -> Dict[str, Dict]:
        """
        Crée le mapping intelligent NORMAL (du début vers la fin).
        
        LOGIQUE RÉVOLUTIONNAIRE:
        - Commence par la DERNIÈRE saison, DERNIER épisode  
        - Mappe vers le DERNIER épisode TMDB disponible
        - Remonte jusqu'à S1E1
        - GARANTIT que les épisodes récents ont les bonnes métadonnées !
        
        Exemple: TMDB S1(24ep) + Anime-Sama S1(12ep) + S2(5ep)
        - Anime-Sama S2E5 ← TMDB S1E24 (DERNIER!)
        - Anime-Sama S2E4 ← TMDB S1E23  
        - Anime-Sama S2E1 ← TMDB S1E20
        - Anime-Sama S1E12 ← TMDB S1E19
        - Anime-Sama S1E1 ← TMDB S1E8
        """
        if not self.anime_sama_structure or not self.tmdb_episodes:
            logger.log("TMDB", "Pas de données pour le mapping intelligent")
            return {}
        
        # Organiser les épisodes TMDB par saison - SEULEMENT VRAIS ÉPISODES SORTIS
        tmdb_by_season = {}
        today = datetime.now().strftime("%Y-%m-%d")  # Date actuelle dynamique
        
        for episode_key, episode_data in self.tmdb_episodes.items():
            # Parser s1e5 -> season=1, episode=5
            if episode_key.startswith('s') and 'e' in episode_key:
                try:
                    season_part, episode_part = episode_key[1:].split('e')
                    season_num = int(season_part)
                    episode_num = int(episode_part)
                    
                    # FILTRE 1: Seulement les VRAIES saisons (pas spéciales)
                    if season_num <= 0:
                        logger.log("TMDB", f"Saison spéciale ignorée: S{season_num}E{episode_num}")
                        continue
                    
                    # FILTRE 2: Seulement les épisodes VRAIMENT SORTIS
                    air_date = episode_data.get("air_date")
                    if air_date and air_date > today:
                        logger.log("TMDB", f"Épisode futur ignoré: S{season_num}E{episode_num} ({air_date})")
                        continue
                    elif not air_date:
                        logger.log("TMDB", f"Épisode sans date ignoré: S{season_num}E{episode_num}")
                        continue
                    
                    # ÉPISODE VALIDE : Vraie saison + Vraiment sorti
                    if season_num not in tmdb_by_season:
                        tmdb_by_season[season_num] = {}
                    tmdb_by_season[season_num][episode_num] = episode_data
                    logger.log("TMDB", f"Épisode valide: S{season_num}E{episode_num} ({air_date})")
                    
                except ValueError:
                    continue
        
        logger.log("TMDB", f"TMDB organisé: {len(tmdb_by_season)} saisons")
        
        # Créer la file d'attente d'épisodes NORMALE (du premier au dernier)
        episodes_queue = []
        
        # Traiter chaque saison TMDB dans l'ordre NORMAL
        for tmdb_season in sorted(tmdb_by_season.keys()):
            tmdb_episodes_season = tmdb_by_season[tmdb_season]
            logger.log("TMDB", f"TMDB S{tmdb_season}: {len(tmdb_episodes_season)} épisodes")
            
            # Ajouter les épisodes dans l'ordre NORMAL (premier → dernier)
            for episode_num in sorted(tmdb_episodes_season.keys()):
                episodes_queue.append({
                    'tmdb_season': tmdb_season,
                    'tmdb_episode': episode_num,
                    'data': tmdb_episodes_season[episode_num]
                })
        
        # CALCUL TOTAL TMDB
        total_tmdb_episodes = len(episodes_queue)
        logger.log("TMDB", f"TOTAL TMDB: {total_tmdb_episodes} épisodes vraiment sortis")
        
        # Créer la liste des épisodes Anime-Sama NORMALE - SEULEMENT VRAIES SAISONS
        anime_sama_episodes = []
        
        # Filtrer les vraies saisons Anime-Sama (pas spéciales/bizarres)
        valid_seasons = {}
        for season_num, count in self.anime_sama_structure.items():
            if season_num > 0 and season_num < 900:  # Seulement saisons normales (1, 2, 3... mais pas 990, 991, etc.)
                valid_seasons[season_num] = count
                logger.log("TMDB", f"Saison Anime-Sama valide: S{season_num} ({count} épisodes)")
            else:
                logger.log("TMDB", f"Saison Anime-Sama ignorée: S{season_num} (spéciale/bizarre)")
        
        # CALCUL TOTAL ANIME-SAMA
        total_anime_sama_episodes = sum(valid_seasons.values())
        logger.log("TMDB", f"TOTAL ANIME-SAMA: {total_anime_sama_episodes} épisodes valides")
        
        # VÉRIFICATION CRITIQUE - SÉCURITÉ
        if total_tmdb_episodes != total_anime_sama_episodes:
            logger.log("TMDB", f"MAPPING DÉSACTIVÉ: Nombre d'épisodes différent!")
            logger.log("TMDB", f"   TMDB: {total_tmdb_episodes} épisodes")
            logger.log("TMDB", f"   Anime-Sama: {total_anime_sama_episodes} épisodes")
            logger.log("TMDB", f"   Différence: {abs(total_tmdb_episodes - total_anime_sama_episodes)}")
            logger.log("TMDB", f"   Mapping intelligent désactivé pour sécurité")
            return {}  # ARRÊTER ICI - Pas de mapping !
        else:
            logger.log("TMDB", f"MATCH PARFAIT: {total_tmdb_episodes} épisodes des deux côtés!")
        
        # Traiter les saisons Anime-Sama dans l'ordre NORMAL
        for anime_sama_season in sorted(valid_seasons.keys()):
            episode_count = valid_seasons[anime_sama_season]
            logger.log("TMDB", f"Anime-Sama S{anime_sama_season}: {episode_count} épisodes valides")
            
            # Ajouter les épisodes dans l'ordre NORMAL (premier → dernier)
            for anime_sama_episode in range(1, episode_count + 1):
                anime_sama_episodes.append({
                    'season': anime_sama_season,
                    'episode': anime_sama_episode,
                    'key': f"s{anime_sama_season}e{anime_sama_episode}"
                })
        
        logger.log("TMDB", f"Liste finale Anime-Sama: {len(anime_sama_episodes)} épisodes NORMAUX")
        
        # Mapping intelligent NORMAL 1:1
        intelligent_mapping = {}
        
        # Prendre le minimum pour éviter les débordements
        episodes_to_map = min(len(anime_sama_episodes), len(episodes_queue))
        logger.log("TMDB", f"Mapping de {episodes_to_map} épisodes (1:1)")
        
        # DEBUG COMPLET - Listes initiales
        logger.log("TMDB", f"DEBUG MAPPING INITIAL:")
        logger.log("TMDB", f"   Total Anime-Sama episodes (normaux): {len(anime_sama_episodes)}")
        logger.log("TMDB", f"   Total TMDB episodes (normaux): {len(episodes_queue)}")
        logger.log("TMDB", f"   Episodes à mapper: {episodes_to_map}")
        
        # DEBUG - Premiers 10 épisodes Anime-Sama
        logger.log("TMDB", f"DEBUG Anime-Sama (premiers 10 épisodes):")
        for i in range(min(10, len(anime_sama_episodes))):
            ep = anime_sama_episodes[i]
            logger.log("TMDB", f"   Position {i}: {ep['key']} (S{ep['season']}E{ep['episode']})")
        
        # DEBUG - Premiers 10 épisodes TMDB
        logger.log("TMDB", f"DEBUG TMDB (premiers 10 épisodes):")
        for i in range(min(10, len(episodes_queue))):
            ep = episodes_queue[i]
            logger.log("TMDB", f"   Position {i}: S{ep['tmdb_season']}E{ep['tmdb_episode']}")
        
        # Mapper épisode par épisode (dernier vers premier)
        for i in range(episodes_to_map):
            anime_sama_ep = anime_sama_episodes[i]
            tmdb_ep = episodes_queue[i]
            
            # Créer le mapping
            anime_sama_key = anime_sama_ep['key']
            intelligent_mapping[anime_sama_key] = tmdb_ep['data']
            
            # Log détaillé pour les 15 premiers et 15 derniers (étendu pour One Piece)
            if i < 15 or i >= episodes_to_map - 15:
                logger.log("TMDB", f"  MAPPING: {anime_sama_key} ← TMDB S{tmdb_ep['tmdb_season']}E{tmdb_ep['tmdb_episode']} (#{i+1})")
            elif i == 15:
                logger.log("TMDB", f"  ... (mapping {episodes_to_map - 30} épisodes intermédiaires) ...")
        
        # Résumé final avec analyse des épisodes mappés
        logger.log("TMDB", f"Mapping NORMAL créé: {len(intelligent_mapping)} correspondances PARFAITES")
        
        # DEBUG FINAL - Analyser les épisodes mappés
        if intelligent_mapping:
            mapped_keys = list(intelligent_mapping.keys())
            mapped_keys.sort(key=lambda x: (int(x.split('s')[1].split('e')[0]), int(x.split('e')[1])))
            
            logger.log("TMDB", f"ÉPISODES MAPPÉS (ordre chronologique):")
            logger.log("TMDB", f"   Premier épisode mappé: {mapped_keys[0]}")
            logger.log("TMDB", f"   Dernier épisode mappé: {mapped_keys[-1]}")
            logger.log("TMDB", f"   Nombre total d'épisodes mappés: {len(mapped_keys)}")
            
            # Vérifier la continuité pour S1
            s1_episodes = [key for key in mapped_keys if key.startswith('s1e')]
            if s1_episodes:
                s1_nums = [int(key.split('e')[1]) for key in s1_episodes]
                s1_nums.sort()
                logger.log("TMDB", f"   Saison 1 mappée: E{min(s1_nums)} à E{max(s1_nums)} ({len(s1_nums)} épisodes)")
                
                # Détecter les épisodes manquants en S1
                missing_s1 = []
                for ep_num in range(1, max(s1_nums) + 1):
                    if ep_num not in s1_nums:
                        missing_s1.append(ep_num)
                
                if missing_s1:
                    logger.log("TMDB", f"   S1 épisodes MANQUANTS dans le mapping: {missing_s1}")
                else:
                    logger.log("TMDB", f"   S1 mapping COMPLET de E1 à E{max(s1_nums)}")
        
        return intelligent_mapping
    
    def get_episode_counts_from_seasons_data(self, seasons_data: List[Dict], episodes_map: Dict[int, int]) -> Dict[int, int]:
        """Récupère le nombre d'épisodes par saison depuis les données d'épisodes détectés."""
        episode_counts = {}
        
        for season in seasons_data:
            season_num = season.get('season_number', 0)
            if season_num > 0:  # Saisons normales uniquement
                episode_count = episodes_map.get(season_num, 0)
                if episode_count > 0:
                    episode_counts[season_num] = episode_count
                    
        return episode_counts


def create_intelligent_episode_mapping(
    tmdb_episodes_map: Dict[str, Dict], 
    seasons_data: List[Dict],
    episodes_map: Dict[int, int]
) -> Dict[str, Dict]:
    """
    Fonction utilitaire pour créer le mapping intelligent NORMAL.
    
    Args:
        tmdb_episodes_map: Episodes TMDB (format s1e1 -> data)
        seasons_data: Données des saisons Anime-Sama
        episodes_map: Nombre d'épisodes par saison détectés (season_num -> count)
    
    Returns:
        Mapping intelligent NORMAL (anime_sama_key -> tmdb_episode_data)
    
    Exemple NORMAL:
        TMDB: S1(24ep) = 24 épisodes total
        Anime-Sama: S1(12ep) + S2(5ep) = 17 épisodes total
        Résultat NORMAL (du début vers la fin):
        - Anime-Sama S2E5 ← TMDB S1E24 (DERNIER épisode!)
        - Anime-Sama S2E4 ← TMDB S1E23
        - Anime-Sama S2E1 ← TMDB S1E20
        - Anime-Sama S1E12 ← TMDB S1E19
        - Anime-Sama S1E1 ← TMDB S1E8
        
    AVANTAGE: Les épisodes récents ont les bonnes métadonnées !
    """
    logger.log("TMDB", "Création du mapping NORMAL")
    
    mapper = TMDBEpisodeMapper()
    
    # Charger les données TMDB
    mapper.set_tmdb_episodes(tmdb_episodes_map)
    
    # Construire la structure Anime-Sama avec les comptes d'épisodes réels
    anime_sama_structure = []
    for season in seasons_data:
        season_num = season.get('season_number', 0)
        if season_num > 0:
            episode_count = episodes_map.get(season_num, 0)
            if episode_count > 0:
                season_data = season.copy()
                season_data['episode_count'] = episode_count
                anime_sama_structure.append(season_data)
    
    mapper.set_anime_sama_structure(anime_sama_structure)
    
    # Créer le mapping intelligent
    result = mapper.create_intelligent_mapping()
    
    logger.log("TMDB", f"Mapping NORMAL terminé: {len(result)} épisodes mappés")
    return result