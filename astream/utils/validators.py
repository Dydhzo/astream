from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator
import re


class EpisodeRequest(BaseModel):
    """Validation requête d'épisode."""
    anime_id: str = Field(..., pattern=r"^as:[a-z0-9-]+:s\d+e\d+$", 
                         description="ID au format as:anime_slug:s{season}e{episode}")
    language: Optional[str] = Field(None, pattern=r"^(VOSTFR|VF|Tout)$")
    
    @field_validator('anime_id')
    def validate_anime_id(cls, v):
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
        if v and len(v.strip()) == 0:
            raise ValueError('La recherche ne peut pas être vide')
        return v.strip() if v else None


class MetadataRequest(BaseModel):
    """Validation requête métadonnées."""
    anime_id: str = Field(..., pattern=r"^as:[a-z0-9-]+$", 
                         description="ID au format as:anime_slug")
    
    @field_validator('anime_id')
    def validate_anime_id(cls, v):
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
        if isinstance(v, str):
            return [g.strip() for g in v.split(',') if g.strip()]
        return v or []
    
    @field_validator('languages')
    def validate_languages(cls, v):
        if isinstance(v, str):
            return [v] if v else ["VOSTFR"]
        return v or ["VOSTFR"]


class Season(BaseModel):
    """Modèle validation saison."""
    season_number: int = Field(..., ge=0, le=999)
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
        season_numbers = [s.season_number if isinstance(s, Season) else s.get('season_number') for s in v]
        if len(set(season_numbers)) != len(season_numbers):
            raise ValueError('Numéros de saison dupliqués détectés')
        return v


class ConfigModel(BaseModel):
    """Modèle configuration utilisateur via URL."""
    language: Optional[str] = "Tout"  # "Tout", "VOSTFR", "VF"
    languageOrder: Optional[str] = "VOSTFR,VF"  # Ordre des langues pour "Tout"

    @field_validator("language")
    def check_language(cls, v):
        valid_languages = ["Tout", "VOSTFR", "VF"]
        if v not in valid_languages:
            raise ValueError(f"Langue invalide: {valid_languages}")
        return v
    
    @field_validator("languageOrder")
    def check_language_order(cls, v):
        if not v:
            return "VOSTFR,VF"
        
        valid_langs = ["VOSTFR", "VF"]
        langs = [lang.strip().upper() for lang in v.split(',')]
        
        # Vérifier que toutes les langues sont valides
        for lang in langs:
            if lang not in valid_langs:
                return "VOSTFR,VF"  # Fallback si invalide
        
        return ','.join(langs)


default_config = ConfigModel().model_dump()