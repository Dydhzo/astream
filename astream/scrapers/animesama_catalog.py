from typing import List, Optional, Dict, Any
import asyncio
from urllib.parse import quote
from bs4 import BeautifulSoup

from astream.utils.http_client import HttpClient
from astream.utils.logger import logger
from astream.utils.base_scraper import BaseScraper
from astream.utils.database import get_metadata_from_cache, set_metadata_to_cache
from astream.scrapers.animesama_parser import (
    parse_anime_card,
    parse_pepites_card,
    parse_recent_episodes_card,
    parse_sortie_card,
    parse_classique_card,
    is_valid_content_type
)


class AnimeSamaCatalog(BaseScraper):
    """Gestionnaire du catalogue et de la recherche AnimeSama."""
    
    def __init__(self, client: HttpClient):
        super().__init__(client, "https://anime-sama.fr")
        self._detect_all_languages_in_catalog = True
    
    async def get_homepage_content(self) -> List[Dict[str, Any]]:
        """Récupère le contenu de la page d'accueil anime-sama."""
        cache_key = "as:homepage:content"
        cached_data = await get_metadata_from_cache(cache_key)
        if cached_data:
            logger.info(f"🔒 DATABASE: Cache hit {cache_key} - Contenu homepage récupéré")
            return cached_data.get("animes", [])
        
        logger.info(f"🔒 DATABASE: Cache miss {cache_key} - Scraping homepage complet")
        
        try:
            logger.info("🐍 ANIMESAMA: Récupération complète de la homepage")
            response = await self._rate_limited_request('get', f"{self.base_url}/")
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            all_animes = []
            seen_slugs = set()
            
            recent_episodes = await self._scrape_recent_episodes(soup, seen_slugs)
            all_animes.extend(recent_episodes)
            logger.info(f"🐍 ANIMESAMA: Derniers épisodes ajoutés: {len(recent_episodes)} items")
            
            new_releases = await self._scrape_new_releases(soup, seen_slugs)
            all_animes.extend(new_releases)
            logger.info(f"🐍 ANIMESAMA: Derniers contenus sortis: {len(new_releases)} items")
            
            classics = await self._scrape_classics(soup, seen_slugs)
            all_animes.extend(classics)
            logger.info(f"🐍 ANIMESAMA: Les classiques: {len(classics)} items")
            
            pepites = await self._scrape_pepites(soup, seen_slugs)
            all_animes.extend(pepites)
            logger.info(f"🐍 ANIMESAMA: Découvrez des pépites: {len(pepites)} items")
            
            logger.info(f"💡 INFO: Total homepage: {len(all_animes)} animes/films récupérés")
            
            if self._detect_all_languages_in_catalog and all_animes:
                all_animes = await self._enhance_animes_with_languages(all_animes)
            
            cache_data = {"animes": all_animes, "total": len(all_animes)}
            await set_metadata_to_cache(cache_key, cache_data)
            logger.info(f"🔒 DATABASE: Cache set {cache_key} - {len(all_animes)} animes")
            
            return all_animes
            
        except Exception as e:
            logger.error(f"🐍 ANIMESAMA: Échec récupération homepage: {e}")
            return []

    async def search_anime(self, query: str, language: Optional[str] = None, genre: Optional[str] = None) -> List[Dict[str, Any]]:
        """Recherche des animes sur anime-sama."""
        cache_key = f"as:search:{query}"
        if genre:
            cache_key += f":genre-{genre}"
        
        cached_data = await get_metadata_from_cache(cache_key)
        if cached_data:
            logger.info(f"🔒 DATABASE: Cache hit {cache_key} - Résultats recherche")
            return cached_data.get("results", [])
        
        logger.info(f"🔒 DATABASE: Cache miss {cache_key} - Recherche live")
        
        try:
            all_results = []
            
            types_to_search = ["Anime", "Film"]
            
            for content_type in types_to_search:
                try:
                    search_url = f"{self.base_url}/catalogue/?search={quote(query)}"
                    
                    if language and language in ["VOSTFR", "VF"]:
                        search_url += f"&langue[]={language}"
                    
                    if genre:
                        search_url += f"&genre[]={quote(genre)}"
                    
                    search_url += f"&type[]={content_type}"
                    
                    logger.debug(f"🔍 DEBUG: Recherche {content_type.lower()}: {search_url}")
                    response = await self._rate_limited_request('get', search_url)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    anime_cards = soup.find_all('a', href=lambda x: x and '/catalogue/' in x)
                    
                    for card in anime_cards:
                        anime_data = parse_anime_card(card)
                        if anime_data:
                            all_results.append(anime_data)
                
                except Exception as e:
                    logger.warning(f"🐍 ANIMESAMA: Erreur recherche {content_type}: {e}")
                    continue
            
            logger.info(f"💡 INFO: Trouvé {len(all_results)} résultats pour '{query}'")
            
            if all_results and self._detect_all_languages_in_catalog:
                all_results = await self._enhance_animes_with_languages(all_results)
            
            cache_data = {"results": all_results, "query": query, "total_found": len(all_results)}
            await set_metadata_to_cache(cache_key, cache_data)
            logger.info(f"🔒 DATABASE: Cache set {cache_key} - {len(all_results)} résultats")
            
            return all_results
            
        except Exception as e:
            logger.error(f"🐍 ANIMESAMA: Échec recherche anime: {e}")
            return []

    async def _enhance_animes_with_languages(self, animes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrichit une liste d'animes avec toutes leurs langues disponibles."""
        try:
            
            async def enhance_anime_with_all_languages(anime):
                """Enrichit un anime avec toutes ses langues disponibles."""
                slug = anime.get('slug')
                if slug:
                    all_languages = await self._detect_all_languages_for_anime(slug)
                    anime['languages'] = all_languages
                return anime
            
            enhanced_animes = await asyncio.gather(*[enhance_anime_with_all_languages(anime) for anime in animes])
            return enhanced_animes
            
        except Exception as e:
            logger.warning(f"🐍 ANIMESAMA: Erreur enrichissement langues: {e}")
            return animes

    async def _detect_all_languages_for_anime(self, anime_slug: str) -> List[str]:
        """Détecte toutes les langues disponibles pour un anime depuis sa page détaillée."""
        try:
            from astream.scrapers.animesama_parser import parse_languages_from_html
            
            response = await self._internal_request('get', f"{self.base_url}/catalogue/{anime_slug}/")
            response.raise_for_status()
            
            languages = parse_languages_from_html(response.text)
            return languages
            
        except Exception as e:
            return ["VOSTFR"]
    
    async def _scrape_recent_episodes(self, soup: BeautifulSoup, seen_slugs: set) -> List[Dict[str, Any]]:
        """Scrape la section 'Derniers épisodes ajoutés'."""
        try:
            animes = []
            container = soup.find('div', id='containerAjoutsAnimes')
            if not container:
                return []
            
            anime_cards = container.find_all('a', href=lambda x: x and '/catalogue/' in x)
            
            for card in anime_cards:
                anime_data = parse_recent_episodes_card(card)
                if anime_data and anime_data['slug'] not in seen_slugs:
                    seen_slugs.add(anime_data['slug'])
                    animes.append(anime_data)
            
            return animes
            
        except Exception as e:
            logger.warning(f"🐍 ANIMESAMA: Erreur scraping derniers épisodes: {e}")
            return []
    
    async def _scrape_new_releases(self, soup: BeautifulSoup, seen_slugs: set) -> List[Dict[str, Any]]:
        """Scrape la section 'Derniers contenus sortis'."""
        try:
            animes = []
            container = soup.find('div', id='containerSorties')
            if not container:
                return []
            
            anime_cards = container.find_all('div', class_='shrink-0')
            
            for card in anime_cards:
                anime_data = parse_sortie_card(card)
                if anime_data and is_valid_content_type(anime_data.get('type', '')) and anime_data['slug'] not in seen_slugs:
                    seen_slugs.add(anime_data['slug'])
                    animes.append(anime_data)
            
            return animes
            
        except Exception as e:
            logger.warning(f"🐍 ANIMESAMA: Erreur scraping nouveaux contenus: {e}")
            return []
    
    async def _scrape_classics(self, soup: BeautifulSoup, seen_slugs: set) -> List[Dict[str, Any]]:
        """Scrape la section 'Les classiques'."""
        try:
            animes = []
            container = soup.find('div', id='containerClassiques')
            if not container:
                return []
            
            anime_cards = container.find_all('div', class_='shrink-0')
            
            for card in anime_cards:
                anime_data = parse_classique_card(card)
                if anime_data and is_valid_content_type(anime_data.get('type', '')) and anime_data['slug'] not in seen_slugs:
                    seen_slugs.add(anime_data['slug'])
                    animes.append(anime_data)
            
            return animes
            
        except Exception as e:
            logger.warning(f"🐍 ANIMESAMA: Erreur scraping classiques: {e}")
            return []
    
    async def _scrape_pepites(self, soup: BeautifulSoup, seen_slugs: set) -> List[Dict[str, Any]]:
        """Scrape la section 'Découvrez des pépites'."""
        try:
            animes = []
            container = soup.find('div', id='containerPepites')
            if not container:
                return []
            
            anime_cards = container.find_all('a', href=lambda x: x and '/catalogue/' in x)
            
            for card in anime_cards:
                anime_data = parse_pepites_card(card)
                if anime_data and is_valid_content_type(anime_data.get('type', '')) and anime_data['slug'] not in seen_slugs:
                    seen_slugs.add(anime_data['slug'])
                    animes.append(anime_data)
            
            return animes
            
        except Exception as e:
            logger.warning(f"🐍 ANIMESAMA: Erreur scraping pépites: {e}")
            return []