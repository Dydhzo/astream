import re
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup

from astream.utils.logger import logger


PANNEAU_ANIME_PATTERN = re.compile(r'panneauAnime\("(.+?)", *"(.+?)"\);')
NEWSPF_PATTERN = re.compile(r'newSPF\("([^"]+)"\)')
SEASON_PATTERNS = [
    re.compile(r'saison\s*(\d+)(?:-(\d+))?'),
    re.compile(r'season\s*(\d+)(?:-(\d+))?'),
    re.compile(r'saga\s*(\d+)(?:-(\d+))?'),
    re.compile(r's(\d+)(?:-(\d+))?')
]

VIDEO_URL_PATTERNS = [
    re.compile(r'''['"]([^'"]*\.m3u8\?[^'"]*)['"]'''),  # n'importe-quoi.m3u8?n'importe-quoi
    re.compile(r'''['"]([^'"]*\.mp4\?[^'"]*)['"]''')    # n'importe-quoi.mp4?n'importe-quoi
]

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
            
        logger.log("DEBUG", f"Langues détectées: {languages}")
        return languages
        
    except Exception as e:
        logger.log("WARNING", f"Erreur détection langue: {e}")
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
        logger.log("WARNING", f"Erreur extraction slug: {e}")
        return None


def parse_season_info(season_text: str) -> Dict[str, Any]:
    """Parse les informations de saison depuis du texte."""
    try:
        season_lower = season_text.lower()
        
        if any(term in season_lower for term in ['film', 'movie']):
            return {
                'season_number': 998,
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
                'season_number': 999,
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
        logger.log("WARNING", f"Erreur parse saison '{season_text}': {e}")
        return {
            'season_number': 1,
            'sub_season': None,
            'content_type': 'anime',
            'original_text': season_text
        }


def extract_video_urls_from_text(text: str) -> List[str]:
    """Extrait les URLs vidéo depuis du texte."""
    urls = []
    
    for pattern in VIDEO_URL_PATTERNS:
        matches = pattern.findall(text)
        urls.extend(matches)
    
    unique_urls = list(set(urls))
    valid_urls = [url for url in unique_urls if is_valid_video_url(url)]
    
    logger.log("DEBUG", f"URLs vidéo extraites: {len(valid_urls)}")
    return valid_urls


def is_valid_video_url(url: str) -> bool:
    """Vérifie si une URL vidéo est valide."""
    try:
        from astream.config.app_settings import settings
        invalid_patterns = [
            f'{settings.ANIMESAMA_URL}/templates/',
            f'{settings.ANIMESAMA_URL}/assets/',
            '.css',
            '.js',
            '.png',
            '.jpg',
            '.jpeg',
            '.gif'
        ]
        
        url_lower = url.lower()
        return not any(pattern in url_lower for pattern in invalid_patterns)
        
    except Exception:
        return False


def extract_episodes_from_js(js_content: str) -> List[str]:
    """Extrait les URLs d'épisodes depuis le contenu JavaScript."""
    try:
        episodes = []
        
        matches = EPISODES_PATTERN.findall(js_content)
        
        for match in matches:
            episode_urls = re.findall(r"['\"]([^'\"]+)['\"]", match)
            episodes.extend(episode_urls)
        
        valid_episodes = [url for url in episodes if is_valid_video_url(url)]
        
        logger.log("DEBUG", f"Épisodes extraits du JS: {len(valid_episodes)}")
        return valid_episodes
        
    except Exception as e:
        logger.log("WARNING", f"Erreur extraction épisodes JS: {e}")
        return []


def clean_anime_title(title: str) -> str:
    """Nettoie et normalise un titre d'anime."""
    try:
        cleaned = title.strip()
        
        cleaned = re.sub(r'\s+\((?:VOSTFR|VF|SUB|DUB)\)$', '', cleaned, flags=re.IGNORECASE)
        
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        return cleaned.strip()
        
    except Exception as e:
        logger.log("WARNING", f"Erreur nettoyage titre '{title}': {e}")
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
                genre_list = re.split(r'[,;-]+', genre_text)
                genres.extend([g.strip().title() for g in genre_list if g.strip()])
        
        unique_genres = list(set([g for g in genres if len(g) > 1]))
        
        logger.log("DEBUG", f"Genres extraits: {unique_genres}")
        return unique_genres
        
    except Exception as e:
        logger.log("WARNING", f"Erreur extraction genres: {e}")
        return []


def create_seasons_dict(seasons: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """Crée un dictionnaire optimisé pour la recherche de saisons O(1)."""
    seasons_dict = {}
    
    for season in seasons:
        season_num = season.get('season_number')
        if season_num is not None:
            seasons_dict[season_num] = season
    
    return seasons_dict