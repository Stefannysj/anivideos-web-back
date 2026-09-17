from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class HealthResponse(ApiModel):
    status: Literal['ok']
    service: Literal['anivideos-api']
    database: Literal['ok']
    database_engine: Literal['sqlite'] = Field(serialization_alias='databaseEngine')


class ContentItemResponse(ApiModel):
    id: str
    title: str
    category: Literal['anime', 'k-drama', 'series', 'movie']
    category_label: str = Field(serialization_alias='categoryLabel')
    year: int
    score: float
    maturity: str
    format: str
    genres: list[str]
    artwork: str


class CatalogResponse(ApiModel):
    items: list[ContentItemResponse]


class BannerResponse(ApiModel):
    id: str
    category: Literal['Anime', 'K-Drama', 'Serie', 'Película']
    eyebrow: str
    title: str
    synopsis: str
    year: int
    age_rating: str = Field(serialization_alias='ageRating')
    format: str
    genres: list[str]
    artwork: str
    section_href: str = Field(serialization_alias='sectionHref')


class BannerListResponse(ApiModel):
    items: list[BannerResponse]
