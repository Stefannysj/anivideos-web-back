from __future__ import annotations

import re
from typing import Literal

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

_USERNAME_RE = re.compile(r'^[A-Za-z0-9_.-]{3,30}$')


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


class RegisterRequest(ApiModel):
    username: str
    email: str
    password: SecretStr

    @field_validator('username')
    @classmethod
    def valid_username(cls, value: str) -> str:
        normalized = value.strip()
        if not _USERNAME_RE.fullmatch(normalized):
            raise ValueError('Use 3-30 caracteres: letras, números, punto, guion o guion bajo.')
        return normalized

    @field_validator('email')
    @classmethod
    def valid_email(cls, value: str) -> str:
        try:
            result = validate_email(value.strip(), check_deliverability=False)
        except EmailNotValidError as exc:
            raise ValueError('Correo electrónico inválido.') from exc
        return result.normalized.lower()

    @field_validator('password')
    @classmethod
    def valid_password(cls, value: SecretStr) -> SecretStr:
        password = value.get_secret_value()
        if not 10 <= len(password) <= 128:
            raise ValueError('La contraseña debe tener entre 10 y 128 caracteres.')
        if not any(character.isalpha() for character in password) or not any(character.isdigit() for character in password):
            raise ValueError('La contraseña debe incluir al menos una letra y un número.')
        return value


class LoginRequest(ApiModel):
    identifier: str = Field(min_length=3, max_length=254)
    password: SecretStr

    @field_validator('identifier')
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        return value.strip()

    @field_validator('password')
    @classmethod
    def bounded_password(cls, value: SecretStr) -> SecretStr:
        password = value.get_secret_value()
        if not 1 <= len(password) <= 128:
            raise ValueError('Credenciales inválidas.')
        return value


class UserResponse(ApiModel):
    id: int
    username: str
    email: str
    avatar_url: str | None = Field(default=None, serialization_alias='avatarUrl')
    created_at: str = Field(serialization_alias='createdAt')


class AuthResponse(ApiModel):
    user: UserResponse


class MessageResponse(ApiModel):
    message: str
