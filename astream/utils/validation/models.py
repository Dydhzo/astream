from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator
import re
from astream.scrapers.animesama.helpers import parse_genres_string


class EpisodeRequest(BaseModel):
    """Validation requête d'épisode."""
    anime_id: str = Field(..., pattern=r"^as:[a-z0-9-]+:s\d+e\d+$", 
                         description="ID au format as:anime_slug:s{season}e{episode}")
    language: Optional[str] = Field(None, pattern=r"^(VOSTFR|VF|Tout)$")
    
    @field_validator('anime_id')
    def validate_anime_id(cls, v):
        """Valide le format de l'ID d'épisode."""
        if not re.match(r'^as:[a-z0-9-]+:s\d+e\d+$', v):
            raise ValueError('Format anime_id invalide. Attendu: as:anime_slug:s{season}e{episode}')
        return v


class CatalogRequest(BaseModel):
    """Validation requête catalogue."""
    search: Optional[str] = Field(None, min_length=1, max_length=100)
    genre: Optional[str] = Field(None, min_length=1, max_length=50)
    language: Optional[str] = Field(None, pattern=r"^(VOSTFR|VF|Tout)$")
    
    @field_validator('search')
    def validate_search(cls, v):
        """Valide et nettoie le terme de recherche."""
        if v and len(v.strip()) == 0:
            raise ValueError('La recherche ne peut pas être vide')
        return v.strip() if v else None


class MetadataRequest(BaseModel):
    """Validation requête métadonnées."""
    anime_id: str = Field(..., pattern=r"^as:[a-z0-9-]+$", 
                         description="ID au format as:anime_slug")
    
    @field_validator('anime_id')
    def validate_anime_id(cls, v):
        """Valide le format de l'ID anime."""
        if not re.match(r'^as:[a-z0-9-]+$', v):
            raise ValueError('Format anime_id invalide. Attendu: as:anime_slug')
        return v


class ConfigRequest(BaseModel):
    """Validation configuration utilisateur."""
    language: str = Field(default="Tout", pattern=r"^(VOSTFR|VF|Tout)$")


class AnimeCard(BaseModel):
    """Modèle validation carte anime."""
    slug: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    image: str = Field(default="")
    genres: Union[str, List[str]] = Field(default="")
    languages: Union[str, List[str]] = Field(default="VOSTFR")
    type: str = Field(default="anime")
    
    @field_validator('genres')
    def validate_genres(cls, v):
        """Convertit les genres en liste si nécessaire."""
        if isinstance(v, str):
            return parse_genres_string(v)
        return v or []
    
    @field_validator('languages')
    def validate_languages(cls, v):
        """Normalise les langues en liste."""
        if isinstance(v, str):
            return [v] if v else ["VOSTFR"]
        return v or ["VOSTFR"]


class Season(BaseModel):
    """Modèle validation saison."""
    season_number: int = Field(..., ge=0, le=991)
    name: str = Field(..., min_length=1)
    path: str = Field(default="")
    languages: List[str] = Field(default_factory=list)
    sub_seasons: List[Dict[str, Any]] = Field(default_factory=list)
    episode_counts: Optional[Dict[str, int]] = Field(default_factory=dict)
    total_episodes: Optional[int] = Field(default=0, ge=0)


class AnimeDetails(BaseModel):
    """Modèle validation détails anime."""
    slug: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    synopsis: str = Field(default="")
    image: str = Field(default="")
    genres: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    type: str = Field(default="anime")
    seasons: List[Season] = Field(default_factory=list)
    
    @field_validator('seasons')
    def validate_seasons(cls, v):
        """Vérifie l'unicité des numéros de saisons."""
        season_numbers = [s.season_number if isinstance(s, Season) else s.get('season_number') for s in v]
        if len(set(season_numbers)) != len(season_numbers):
            raise ValueError('Numéros de saison dupliqués détectés')
        return v


class ConfigModel(BaseModel):
    """Modèle configuration utilisateur via URL."""
    language: Optional[str] = "Tout"  # "Tout", "VOSTFR", "VF"
    languageOrder: Optional[str] = "VOSTFR,VF"  # Ordre des langues pour "Tout"
    tmdbApiKey: Optional[str] = None  # Clé API TMDB utilisateur
    tmdbEnabled: Optional[bool] = True  # Activer/désactiver TMDB
    tmdbEpisodeMapping: Optional[bool] = False  # Mapping intelligent épisodes
    userExcludedDomains: Optional[str] = ""  # Exclusions utilisateur (patterns séparés par virgules)

    @field_validator("language")
    def check_language(cls, v):
        """Vérifie la validité de la langue sélectionnée."""
        valid_languages = ["Tout", "VOSTFR", "VF"]
        if v not in valid_languages:
            raise ValueError(f"Langue invalide: {valid_languages}")
        return v
    
    @field_validator("languageOrder")
    def check_language_order(cls, v):
        """Valide et normalise l'ordre des langues."""
        if not v:
            return "VOSTFR,VF"
        
        valid_langs = ["VOSTFR", "VF"]
        langs = [lang.strip().upper() for lang in v.split(',')]
        
        # Vérifier que toutes les langues sont valides
        for lang in langs:
            if lang not in valid_langs:
                return "VOSTFR,VF"  # Fallback si invalide
        
        return ','.join(langs)
    
    @field_validator("tmdbApiKey")
    def check_tmdb_api_key(cls, v):
        """Valide la clé API TMDB."""
        if v and len(v.strip()) < 10:
            raise ValueError("Clé API TMDB invalide")
        return v.strip() if v else None
    
    @field_validator("userExcludedDomains")
    def check_user_excluded_domains(cls, v):
        """Valide et nettoie les domaines exclus."""
        if not v:
            return ""
        
        # Vérifier qu'il n'y a pas d'espaces
        if ' ' in v:
            raise ValueError("Espaces non autorisés dans les exclusions")
        
        # Nettoyer et valider les patterns
        patterns = [pattern.strip() for pattern in v.split(',') if pattern.strip()]
        
        # Vérifier que chaque pattern est valide (pas vide après nettoyage)
        valid_patterns = [p for p in patterns if p and len(p) > 0]
        
        return ','.join(valid_patterns)


default_config = ConfigModel().model_dump()