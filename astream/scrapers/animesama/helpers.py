import re
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup

from astream.utils.logger import logger


# Pattern pour extraire les saisons depuis JavaScript
PANNEAU_ANIME_PATTERN = re.compile(r'panneauAnime\("(.+?)", *"(.+?)"\);')
# Pattern pour extraire les titres de films
NEWSPF_PATTERN = re.compile(r'newSPF\("([^"]+)"\)')
# Patterns pour détecter les numéros de saisons
SEASON_PATTERNS = [
    re.compile(r'saison\s*(\d+)(?:-(\d+))?'),
    re.compile(r'season\s*(\d+)(?:-(\d+))?'),
    re.compile(r'saga\s*(\d+)(?:-(\d+))?'),
    re.compile(r's(\d+)(?:-(\d+))?')
]

# Patterns pour extraire les URLs vidéo (EXIGE / avant extension)
VIDEO_URL_PATTERNS = [
    re.compile(r'''['"]([^'"]*\/[^'"]*\.m3u8[^'"]*)['"]'''),   # EXIGE / avant .m3u8
    re.compile(r'''['"]([^'"]*\/[^'"]*\.mp4[^'"]*)['"]'''),    # EXIGE / avant .mp4
    re.compile(r'''['"]([^'"]*\/[^'"]*\.mkv[^'"]*)['"]''')     # EXIGE / avant .mkv
]

# Pattern pour extraire les épisodes depuis JavaScript
EPISODES_PATTERN = re.compile(r'var\s+eps\w*\s*=\s*\[([^\]]+)\]')


def detect_language_from_card(card_element) -> List[str]:
    """Détecte langues depuis élément carte HTML."""
    try:
        languages = []
        card_text = card_element.get_text().lower()
        
        if 'vostfr' in card_text:
            languages.append('VOSTFR')
        if any(term in card_text for term in ['vf', 'french', 'français']):
            languages.append('VF')
        
        if not languages:
            languages.append('VOSTFR')
            
        logger.debug(f"Langues détectées: {languages}")
        return languages
        
    except Exception as e:
        logger.warning(f"Erreur détection langue: {e}")
        return ['VOSTFR']


def build_animesama_url(base_url: str, anime_slug: str, path: str, language: str = "") -> str:
    """Construit URL AnimeSama formatée."""
    if language and path:
        return f"{base_url}/catalogue/{anime_slug}/{path}/{language}/"
    elif path:
        return f"{base_url}/catalogue/{anime_slug}/{path}/"
    else:
        return f"{base_url}/catalogue/{anime_slug}/"


def extract_anime_slug_from_url(url: str) -> Optional[str]:
    """Extrait le slug anime depuis une URL."""
    try:
        if '/catalogue/' in url:
            if url.startswith('https://'):
                slug = url.split('/catalogue/')[-1].rstrip('/')
            else:
                slug = url.split('/catalogue/')[-1].rstrip('/') if url.startswith('/catalogue/') else url.split('/')[-1]
            
            parts = slug.split('/')
            return parts[0] if parts else None
        return None
    except Exception as e:
        logger.warning(f"Erreur extraction slug: {e}")
        return None


def parse_season_info(season_text: str) -> Dict[str, Any]:
    """Parse les informations de saison depuis du texte."""
    try:
        season_lower = season_text.lower()
        
        if any(term in season_lower for term in ['film', 'movie']):
            return {
                'season_number': 990,
                'sub_season': None,
                'content_type': 'film',
                'original_text': season_text
            }
        elif any(term in season_lower for term in ['special', 'oav', 'ova']):
            return {
                'season_number': 0,
                'sub_season': None,
                'content_type': 'special',
                'original_text': season_text
            }
        elif any(term in season_lower for term in ['hors-série', 'hors serie']):
            return {
                'season_number': 991,
                'sub_season': None,
                'content_type': 'hors-serie',
                'original_text': season_text
            }
        
        for pattern in SEASON_PATTERNS:
            match = pattern.search(season_lower)
            if match:
                main_season = int(match.group(1))
                sub_season = int(match.group(2)) if match.group(2) else None
                
                return {
                    'season_number': main_season,
                    'sub_season': sub_season,
                    'content_type': 'anime',
                    'original_text': season_text
                }
        
        return {
            'season_number': 1,
            'sub_season': None,
            'content_type': 'anime',
            'original_text': season_text
        }
        
    except Exception as e:
        logger.warning(f"Erreur parse saison '{season_text}': {e}")
        return {
            'season_number': 1,
            'sub_season': None,
            'content_type': 'anime',
            'original_text': season_text
        }


def extract_video_urls_from_text(text: str, source_url: str) -> List[str]:
    """Extrait la PREMIÈRE URL vidéo valide (format: ://host/ + extension) - S'ARRÊTE dès qu'elle en trouve une."""
    urls = []
    
    for pattern in VIDEO_URL_PATTERNS:
        matches = pattern.findall(text)
        urls.extend(matches)
    
    unique_urls = list(set(urls))
    
    # Extraire le host de la source
    source_host = ""
    if "://" in source_url:
        source_host = source_url.split("://")[1].split("/")[0]
    
    # Chercher la PREMIÈRE URL valide et S'ARRÊTER
    for url in unique_urls:
        # Vérifier format: ://host/ + extension vidéo
        if "://" not in url:
            continue
            
        # Extraire le host de l'URL trouvée
        found_host = url.split("://")[1].split("/")[0]
        
        # Host différent obligatoire
        if found_host == source_host:
            logger.debug(f"URL ignorée (même host): {url}")
            continue
        
        # Extension vidéo obligatoire
        if not any(ext in url for ext in ['.m3u8', '.mp4', '.mkv']):
            continue
            
        # PREMIÈRE URL valide trouvée → STOP !
        logger.debug(f"PREMIÈRE URL valide trouvée - ARRÊT: {url}")
        return [url]
    
    # Aucune URL valide trouvée
    logger.debug(f"Aucune URL vidéo valide trouvée")
    return []


def extract_episodes_from_js(js_content: str) -> List[str]:
    """Extrait les URLs d'épisodes depuis le contenu JavaScript."""
    try:
        episodes = []
        
        matches = EPISODES_PATTERN.findall(js_content)
        
        for match in matches:
            episode_urls = re.findall(r"['\"]([^'\"]+)['\"]", match)
            episodes.extend(episode_urls)
        
        # Filtrer les URLs valides (qui contiennent ://)
        valid_episodes = [url for url in episodes if "://" in url]
        
        logger.debug(f"Épisodes extraits du JS: {len(valid_episodes)}")
        return valid_episodes
        
    except Exception as e:
        logger.warning(f"Erreur extraction épisodes JS: {e}")
        return []


def clean_anime_title(title: str) -> str:
    """Nettoie et normalise un titre d'anime."""
    try:
        cleaned = title.strip()
        
        cleaned = re.sub(r'\s+\((?:VOSTFR|VF|SUB|DUB)\)$', '', cleaned, flags=re.IGNORECASE)
        
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        return cleaned.strip()
        
    except Exception as e:
        logger.warning(f"Erreur nettoyage titre '{title}': {e}")
        return title


def extract_genres_from_text(text: str) -> List[str]:
    """Extrait les genres depuis du texte."""
    try:
        genre_patterns = [
            r'Genre[s]?\s*:\s*([^\n\r]+)',
            r'Catégorie[s]?\s*:\s*([^\n\r]+)',
            r'Type[s]?\s*:\s*([^\n\r]+)'
        ]
        
        genres = []
        text_lower = text.lower()
        
        for pattern in genre_patterns:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                genre_text = match.group(1)
                genre_list = re.split(r'[,;/-]+', genre_text)
                genres.extend([g.strip().title() for g in genre_list if g.strip()])
        
        unique_genres = list(set([g for g in genres if len(g) > 1]))
        
        logger.debug(f"Genres extraits: {unique_genres}")
        return unique_genres
        
    except Exception as e:
        logger.warning(f"Erreur extraction genres: {e}")
        return []


def is_genres_text(text: str) -> bool:
    """Détecte intelligemment si un texte contient des genres (anti-phrase)."""
    if not text or len(text.strip()) < 5:
        return False
        
    import re
    
    # 1. Doit contenir des séparateurs
    has_separators = any(sep in text for sep in [',', ' - ', ' / '])
    if not has_separators:
        return False
    
    # 2. Split et analyser les parties
    parts = re.split(r'[,;/-]+', text)
    parts = [p.strip() for p in parts if p.strip()]
    
    # 3. Minimum 2 parties (sinon pas une liste)
    if len(parts) < 2:
        return False
    
    # 4. Anti-phrase : chaque partie doit être COURTE (1-3 mots max)
    for part in parts:
        words = part.split()
        if len(words) > 3:  # Plus de 3 mots = phrase, pas genre
            return False
        # Éviter les phrases avec articles/prépositions
        if any(word.lower() in ['le', 'la', 'les', 'de', 'du', 'des', 'et', 'ou', 'avec', 'dans'] for word in words):
            return False
    
    # 5. Éviter les patterns de phrase
    if any(bad in text.lower() for bad in ['http', 'www', 'episode', 'saison', 'depuis', 'après']):
        return False
        
    return True


def parse_genres_string(genres_text: str) -> List[str]:
    """Parse les genres depuis une chaîne en gérant virgules ET tirets."""
    if not genres_text:
        return []
    
    import re
    # Utiliser le même pattern que extract_genres_from_text + slash
    genres = re.split(r'[,;/-]+', genres_text)
    return [g.strip() for g in genres if g.strip()]


def create_seasons_dict(seasons: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """Crée un dictionnaire optimisé pour la recherche de saisons O(1)."""
    seasons_dict = {}
    
    for season in seasons:
        season_num = season.get('season_number')
        if season_num is not None:
            seasons_dict[season_num] = season
    
    return seasons_dict