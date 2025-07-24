from typing import List, Optional, Dict, Any
import re
from bs4 import BeautifulSoup

from astream.utils.logger import logger
from astream.utils.animesama_utils import (
    PANNEAU_ANIME_PATTERN, 
    NEWSPF_PATTERN, 
    SEASON_PATTERNS,
    detect_language_from_card,
    extract_anime_slug_from_url,
    parse_season_info,
    clean_anime_title,
    extract_genres_from_text
)


def parse_anime_card(card) -> Optional[Dict[str, Any]]:
    """Parse une carte d'anime à partir du HTML."""
    try:
        href = card.get('href', '')
        if not href or '/catalogue/' not in href:
            return None
        
        # Extraire le slug anime depuis l'URL
        slug = extract_anime_slug_from_url(href)
        if not slug:
            return None
        
        img = card.find('img')
        image_url = img.get('src', '') if img else ''
        
        title = ''
        title_elem = card.find('h1') or card.find('h2')
        if title_elem:
            title = clean_anime_title(title_elem.get_text(strip=True))
        
        card_text = card.get_text()
        text_parts = [part.strip() for part in card_text.split('\n') if part.strip()]
        
        genres = ''
        languages = ''
        content_type = 'anime'
        
        for part in text_parts:
            if ',' in part and any(genre_word in part for genre_word in ['Action', 'Aventure', 'Comédie', 'Drame', 'Romance']) and not genres:
                genres = part
            elif any(lang in part for lang in ['VOSTFR', 'VF']) and not languages:
                languages = part
            elif part.lower() in ['anime', 'film', 'scan']:
                content_type = part.lower()
        
        if title and slug:
            return {
                "slug": slug,
                "title": title,
                "image": image_url,
                "genres": genres,
                "languages": languages,
                "type": content_type
            }
        
        return None
        
    except Exception as e:
        logger.warning(f"🐍 ANIMESAMA: Erreur lors du parsing de la carte anime: {e}")
        return None


def parse_pepites_card(card) -> Optional[Dict[str, Any]]:
    """Parse une carte de la section 'Pépites'."""
    try:
        # Extraire le href du lien
        href = card.get('href', '')
        if not href or '/catalogue/' not in href:
            return None
        
        # Extraire le slug depuis l'URL
        slug = extract_anime_slug_from_url(href)
        if not slug:
            return None
        
        # Trouver l'image
        img = card.find('img', class_='imageCarteHorizontale')
        image_url = img.get('src', '') if img else ''
        
        # Trouver le div d'informations
        info_div = card.find('div', class_='infoCarteHorizontale')
        if not info_div:
            return None
        
        # Extraire le titre depuis h1
        title_elem = info_div.find('h1')
        title = clean_anime_title(title_elem.get_text(strip=True)) if title_elem else ''
        
        # Extraire tous les paragraphes dans l'info div
        paragraphs = info_div.find_all('p')
        
        genres = ''
        content_type = ''
        languages = []
        
        for i, p in enumerate(paragraphs):
            text = p.get_text(strip=True)
            if not text:
                continue
                
            # Structure des pépites : P0=titre alternatifs, P1=genres, P2=type+langues
            if i == 1 and (',' in text or any(genre in text for genre in ['Action', 'Aventure', 'Comédie', 'Drame', 'Romance'])):
                genres = text
            elif i == 2:
                # Ce paragraphe contient type ET langues
                if any(type_word in text.lower() for type_word in ['anime', 'film', 'scans']):
                    for type_word in ['anime', 'film', 'scans']:
                        if type_word in text.lower():
                            content_type = type_word
                            break
                # Extraire les langues du même paragraphe
                if any(lang in text for lang in ['VOSTFR', 'VF']):
                    if 'VOSTFR' in text:
                        languages.append('VOSTFR')
                    if 'VF' in text and 'VOSTFR' not in text:
                        languages.append('VF')
                    elif ', VF' in text or text.endswith('VF'):
                        languages.append('VF')
        
        if not languages:
            languages = ['VOSTFR']  # Défaut
        
        # Vérifier si c'est un contenu valide
        if not is_valid_content_type(content_type):
                return None
        
        
        if title and slug:
            return {
                "slug": slug,
                "title": title,
                "image": image_url,
                "genres": genres,
                "languages": languages,
                "type": content_type
            }
        
        return None
        
    except Exception as e:
        logger.warning(f"🐍 ANIMESAMA: Erreur lors du parsing de la carte Pépites: {e}")
        return None


def parse_anime_details_from_html(soup: BeautifulSoup, anime_slug: str) -> Dict[str, Any]:
    """Parse les détails complets d'un anime depuis HTML."""
    try:
        # Parser les détails de l'anime
        anime_data = {
            "slug": anime_slug,
            "title": "",
            "synopsis": "",
            "image": "",
            "genres": [],
            "languages": "",
            "type": "anime"
        }
        
        # Récupérer le titre depuis h4#titreOeuvre
        title_elem = soup.find('h4', {'id': 'titreOeuvre'})
        if title_elem:
            anime_data["title"] = clean_anime_title(title_elem.get_text(strip=True))
        else:
            # Fallback vers h1 si h4 non trouvé
            title_elem = soup.find('h1')
            if title_elem:
                anime_data["title"] = clean_anime_title(title_elem.get_text(strip=True))
        
        # Récupérer l'image principale depuis img#imgOeuvre ou img#coverOeuvre
        img_elem = soup.find('img', {'id': 'imgOeuvre'}) or soup.find('img', {'id': 'coverOeuvre'})
        if img_elem:
            anime_data["image"] = img_elem.get('src', '')
        
        # Récupérer le synopsis - chercher le <p> qui suit <h2>Synopsis</h2>
        synopsis_header = None
        for h2 in soup.find_all('h2'):
            if 'synopsis' in h2.get_text().lower():
                synopsis_header = h2
                break
        
        if synopsis_header:
            # Chercher le premier <p> après le header Synopsis
            synopsis_elem = synopsis_header.find_next_sibling('p')
            if synopsis_elem:
                anime_data["synopsis"] = synopsis_elem.get_text(strip=True)
        
        # Récupérer les genres - chercher le <a> qui suit <h2>Genres</h2>
        genres_header = None
        for h2 in soup.find_all('h2'):
            if 'genres' in h2.get_text().lower():
                genres_header = h2
                break
        
        if genres_header:
            # Chercher le premier <a> après le header Genres
            genres_elem = genres_header.find_next_sibling('a')
            if genres_elem:
                genres_text = genres_elem.get_text(strip=True)
                anime_data["genres"] = [g.strip() for g in genres_text.split(',') if g.strip()]
        
        return anime_data
        
    except Exception as e:
        logger.warning(f"🐍 ANIMESAMA: Erreur lors du parsing des détails {anime_slug}: {e}")
        return {
            "slug": anime_slug,
            "title": "",
            "synopsis": "",
            "image": "",
            "genres": [],
            "languages": "",
            "type": "anime"
        }


def parse_languages_from_html(html: str) -> List[str]:
    """Détecte les langues disponibles à partir des appels panneauAnime()."""
    try:
        languages = set()
        
        # Détecter les langues depuis les appels panneauAnime()
        panneau_matches = PANNEAU_ANIME_PATTERN.findall(html)
        for name, url in panneau_matches:
            if '/vostfr' in url:
                languages.add('VOSTFR')
            if '/vf' in url:
                languages.add('VF')
            if '/vf1' in url:
                languages.add('VF1')
            if '/vf2' in url:
                languages.add('VF2')
        
        return sorted(languages) if languages else ["VOSTFR"]
        
    except Exception as e:
        logger.warning(f"🐍 ANIMESAMA: Erreur détection langues HTML: {e}")
        return ["VOSTFR"]


def parse_seasons_from_html(html: str, anime_slug: str, base_url: str) -> List[Dict[str, Any]]:
    """Parse les saisons disponibles depuis HTML anime."""
    try:
        seasons = []
        season_mapping = {}
        
        # Utiliser la même méthode que webstreamr : extraire via regex les appels panneauAnime()
        season_matches = PANNEAU_ANIME_PATTERN.findall(html)
        
        if not season_matches:
            logger.warning(f"🐍 ANIMESAMA: Aucun panneauAnime() pour {anime_slug}")
            return []
        
        
        for name, url in season_matches:
            # Ignorer les placeholders/templates
            if name == "nom" and url == "url":
                continue
            
            # Parse le nom de la saison pour déterminer le numéro
            season_info = parse_season_name(name, url)
            if not season_info:
                continue
            
            season_num = season_info["season_number"]
            base_season_num = season_info["base_season_number"]
            
            # Pour les sous-saisons (ex: saison4-2), regrouper dans la saison principale
            main_season_key = base_season_num
            
            if main_season_key not in season_mapping:
                season_mapping[main_season_key] = {
                    "season_number": base_season_num,
                    "name": season_info["display_name"],
                    "path": season_info["path"],
                    "languages": [],
                    "sub_seasons": []  # Pour stocker les sous-saisons
                }
            
            # Détecter les langues depuis l'URL
            languages = extract_languages_from_url(url)
            
            # Ajouter les langues
            for lang in languages:
                if lang not in season_mapping[main_season_key]["languages"]:
                    season_mapping[main_season_key]["languages"].append(lang)
            
            # Si c'est une sous-saison, l'ajouter à la liste
            if season_info.get("is_sub_season"):
                # Construire l'URL complète pour la sous-saison
                sub_season_url = season_info.get("sub_season_url", url)
                if not sub_season_url.startswith('http'):
                    sub_season_url = f"{base_url}/catalogue/{anime_slug}/{sub_season_url}"
                
                sub_season_path = season_info.get("sub_season_path", "")
                season_mapping[main_season_key]["sub_seasons"].append({
                    "name": name,
                    "url": sub_season_url,
                    "path": sub_season_path,  # Ajout du path de la sous-saison
                    "languages": languages
                })
        
        # Convertir en liste
        for season_data in season_mapping.values():
            seasons.append(season_data)
        
        # Trier par numéro de saison
        seasons.sort(key=lambda x: x["season_number"])
        
        return seasons
        
    except Exception as e:
        logger.error(f"🐍 ANIMESAMA: Échec parsing saisons {anime_slug}: {e}")
        return []


def parse_season_name(name: str, url: str) -> Optional[Dict[str, Any]]:
    """Parse le nom d'une saison pour déterminer numéro et type."""
    try:
        # Extraire le path depuis l'URL pour aider à identifier le type
        path = url.split('/')[-2] if '/' in url else ''
        
        # PRIORITÉ : Analyser l'URL en premier (plus fiable que le nom)
        
        # Détecter les saisons normales depuis l'URL (ex: saison1, saison2)
        url_season_match = re.search(r'saison(\d+)$', path)
        if url_season_match:
            season_num = int(url_season_match.group(1))
            return {
                "season_number": season_num,
                "base_season_number": season_num,
                "display_name": f"Saison {season_num}",
                "path": f"saison{season_num}",
                "is_sub_season": False
            }
        
        # Détecter les sous-saisons depuis l'URL (ex: saison3-2)
        url_sub_season_match = re.search(r'saison(\d+)-(\d+)', path)
        if url_sub_season_match:
            base_season = int(url_sub_season_match.group(1))
            sub_part = int(url_sub_season_match.group(2))
            return {
                "season_number": base_season,
                "base_season_number": base_season,
                "display_name": f"Saison {base_season}",
                "path": f"saison{base_season}",
                "is_sub_season": True,
                "sub_season_number": sub_part,
                "sub_season_path": path,  # Ajout du path de la sous-saison
                "sub_season_url": url
            }
        
        # Films
        if 'film' in name.lower() or 'film' in path:
            return {
                "season_number": 998,
                "base_season_number": 998,
                "display_name": "Films",
                "path": "film",
                "is_sub_season": False
            }
        
        # OAV/Spéciaux - Utiliser la saison 0 (convention Stremio)
        if any(x in name.lower() for x in ['oav', 'ova', 'spécial', 'special']) or 'oav' in path:
            return {
                "season_number": 0,
                "base_season_number": 0,
                "display_name": "Spéciaux",
                "path": "oav",
                "is_sub_season": False
            }
        
        # Hors-série
        if 'hs' in path or 'hors' in name.lower():
            hs_match = re.search(r'(\d+)', path)
            if hs_match:
                base_season = int(hs_match.group(1))
                return {
                    "season_number": 999,
                    "base_season_number": 999,
                    "display_name": f"Saison {base_season} HS",
                    "path": f"saison{base_season}hs",
                    "is_sub_season": False
                }
        
        # Saisons normales avec détection des sous-saisons (ex: "Saison 4-2")
        for pattern in SEASON_PATTERNS:
            match = pattern.search(name.lower())
            if match:
                base_season = int(match.group(1))
                sub_season = match.group(2)
                
                if sub_season:
                    # C'est une sous-saison (ex: saison4-2)
                    return {
                        "season_number": base_season,
                        "base_season_number": base_season,
                        "display_name": f"Saison {base_season}",
                        "path": f"saison{base_season}",
                        "is_sub_season": True,
                        "sub_season_number": int(sub_season),
                        "sub_season_path": path,  # Ajout du path de la sous-saison
                        "sub_season_url": url
                    }
                else:
                    # Saison normale
                    return {
                        "season_number": base_season,
                        "base_season_number": base_season,
                        "display_name": f"Saison {base_season}",
                        "path": f"saison{base_season}",
                        "is_sub_season": False
                    }
        
        logger.warning(f"🐍 ANIMESAMA: Parser nom saison impossible: '{name}' (URL: '{url}')")
        return None
        
    except Exception as e:
        logger.warning(f"🐍 ANIMESAMA: Erreur parsing '{name}': {e}")
        return None


def extract_languages_from_url(url: str) -> List[str]:
    """Extrait les langues à partir de l'URL de saison."""
    languages = []
    
    # Patterns pour détecter les langues dans l'URL
    if '/vostfr' in url:
        languages.append('vostfr')
    if '/vf/' in url or url.endswith('/vf'):
        languages.append('vf')
    if '/vf1' in url:
        languages.append('vf1')
    if '/vf2' in url:
        languages.append('vf2')
    
    # Si aucune langue détectée, assumer VOSTFR par défaut
    if not languages:
        languages.append('vostfr')
    
    return languages


def parse_film_titles_from_html(html: str) -> List[str]:
    """Extrait les titres de films via appels newSPF()."""
    try:
        # Extraire les titres des films depuis les appels newSPF("titre")
        film_titles = NEWSPF_PATTERN.findall(html)
        
        logger.debug(f"🔍 DEBUG: Titres films extraits: {film_titles}")
        return [title.strip() for title in film_titles]
        
    except Exception as e:
        logger.warning(f"🐍 ANIMESAMA: Erreur extraction titres films: {e}")
        return []


def is_valid_content_type(content_type: str) -> bool:
    """Vérifie si le type de contenu est valide."""
    if not content_type:
        return False
    content_lower = content_type.lower()
    return "anime" in content_lower or "film" in content_lower


def parse_recent_episodes_card(card) -> Optional[Dict[str, Any]]:
    """Parse une carte de la section 'Derniers épisodes'."""
    try:
        # Récupérer le lien href
        href = card.get('href', '')
        if not href or '/catalogue/' not in href:
            return None
        
        # Extraire le slug depuis l'URL
        slug = extract_anime_slug_from_url(href)
        if not slug:
            return None
        
        # Récupérer l'image
        img_elem = card.find('img')
        image_url = img_elem.get('src', '') if img_elem else ''
        
        # Récupérer le titre
        title_elem = card.find('h1')
        title = clean_anime_title(title_elem.get_text(strip=True)) if title_elem else ''
        
        # Récupérer les boutons pour langues et info épisode
        languages = []
        buttons = card.find_all('button')
        for button in buttons:
            text = button.get_text(strip=True).upper()
            if text in ['VOSTFR', 'VF', 'VF1', 'VF2']:
                languages.append(text)
        
        # Genres vides pour cette section (pas fournis)
        genres = ""
        
        return {
            "slug": slug,
            "title": title,
            "image": image_url,
            "genres": genres,
            "languages": languages,
            "type": "anime"
        }
        
    except Exception as e:
        logger.warning(f"🐍 ANIMESAMA: Erreur parsing carte recent episodes: {e}")
        return None


def parse_sortie_card(card) -> Optional[Dict[str, Any]]:
    """Parse une carte de la section 'Nouvelles sorties'."""
    try:
        # Trouver le lien <a> principal
        link_elem = card if card.name == 'a' else card.find('a')
        if not link_elem:
            return None
            
        href = link_elem.get('href', '')
        if not href or '/catalogue/' not in href:
            return None
        
        # Extraire le slug
        slug = extract_anime_slug_from_url(href)
        if not slug:
            return None
        
        # Récupérer l'image
        img_elem = link_elem.find('img')
        image_url = img_elem.get('src', '') if img_elem else ''
        
        # Récupérer le titre
        title_elem = link_elem.find('h1')
        title = clean_anime_title(title_elem.get_text(strip=True)) if title_elem else ''
        if not title:
            return None
        
        # Récupérer les genres et type depuis les paragraphes
        paragraphs = link_elem.find_all('p')
        genres = ""
        content_type = "anime"
        languages = []
        
        
        for i, p in enumerate(paragraphs):
            text = p.get_text(strip=True)
            if i == 1:  
                genres = text
            elif i == 2:
                # Ce paragraphe contient le type ET les langues
                if any(type_word in text.lower() for type_word in ['anime', 'film', 'scans']):
                    # Si on trouve un type, on l'extrait
                    for type_word in ['anime', 'film', 'scans']:
                        if type_word in text.lower():
                            content_type = type_word
                            break
                # Extraire aussi les langues du même paragraphe
                if ',' in text:
                    langs = [lang.strip() for lang in text.split(',')]
                else:
                    langs = [lang.strip() for lang in text.split()]
                languages = [lang.upper() for lang in langs if lang.upper() in ['VOSTFR', 'VF', 'VF1', 'VF2', 'VASTFR']]
        
        # Vérifier si c'est un contenu valide
        if not is_valid_content_type(content_type):
            return None
        
        
        return {
            "slug": slug,
            "title": title,
            "image": image_url,
            "genres": genres,
            "languages": languages,
            "type": content_type
        }
        
    except Exception as e:
        logger.warning(f"🐍 ANIMESAMA: Erreur parsing carte sortie: {e}")
        return None


def parse_classique_card(card) -> Optional[Dict[str, Any]]:
    """Parse une carte de la section 'Classiques'."""
    return parse_sortie_card(card)