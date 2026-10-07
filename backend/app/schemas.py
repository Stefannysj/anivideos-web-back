from __future__ import annotations

import re
from typing import Literal
import unicodedata

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

_USERNAME_RE = re.compile(r'^[A-Za-z0-9_.-]{3,30}$')
_BIDI_CONTROL = frozenset('\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069')
ContentCategory = Literal['anime', 'k-drama', 'j-drama', 'donghua', 'movie', 'ova']


def _plain_text(value: str, *, field_name: str, allow_newlines: bool) -> str:
    normalized = value.replace('\r\n', '\n').replace('\r', '\n').strip()
    for character in normalized:
        if character in _BIDI_CONTROL:
            raise ValueError(f'{field_name} contiene caracteres de control no permitidos.')
        if unicodedata.category(character) == 'Cc' and not (allow_newlines and character in {'\n', '\t'}):
            raise ValueError(f'{field_name} contiene caracteres de control no permitidos.')
    return normalized


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra='forbid')


class HealthResponse(ApiModel):
    status: Literal['ok']
    service: Literal['anivideos-api']


class PlatformLinkResponse(ApiModel):
    name: str
    url: str
    attribution: str | None = None


class ContentItemResponse(ApiModel):
    id: str
    source: Literal['anilist', 'tmdb']
    source_attribution: str = Field(serialization_alias='sourceAttribution')
    external_id: str = Field(serialization_alias='externalId')
    title: str
    original_title: str | None = Field(default=None, serialization_alias='originalTitle')
    category: ContentCategory
    category_label: str = Field(serialization_alias='categoryLabel')
    year: int | None
    score: float
    maturity: str
    format: str
    genres: list[str]
    artwork: str
    studio: str | None = None
    episodes: int | None = None
    status: str


class ContentDetailResponse(ContentItemResponse):
    synopsis: str
    origin: str
    backdrop_url: str | None = Field(default=None, serialization_alias='backdropUrl')
    trailer_youtube_id: str | None = Field(default=None, serialization_alias='trailerYoutubeId')
    official_url: str | None = Field(default=None, serialization_alias='officialUrl')
    platform_links: list[PlatformLinkResponse] = Field(default_factory=list, serialization_alias='platformLinks')
    source_url: str | None = Field(default=None, serialization_alias='sourceUrl')


class CatalogResponse(ApiModel):
    items: list[ContentItemResponse]


class BannerResponse(ApiModel):
    id: str
    content_id: str = Field(serialization_alias='contentId')
    source: Literal['anilist', 'tmdb']
    source_attribution: str = Field(serialization_alias='sourceAttribution')
    category: str
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


class ProfileUpdateRequest(ApiModel):
    username: str | None = None
    email: str | None = None
    display_name: str | None = Field(default=None, max_length=60, validation_alias='displayName')
    bio: str | None = Field(default=None, max_length=280)
    current_password: SecretStr | None = Field(default=None, max_length=128, validation_alias='currentPassword')

    @field_validator('username')
    @classmethod
    def valid_optional_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not _USERNAME_RE.fullmatch(normalized):
            raise ValueError('Use 3-30 caracteres: letras, números, punto, guion o guion bajo.')
        return normalized

    @field_validator('email')
    @classmethod
    def valid_optional_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            result = validate_email(value.strip(), check_deliverability=False)
        except EmailNotValidError as exc:
            raise ValueError('Correo electrónico inválido.') from exc
        return result.normalized.lower()

    @field_validator('display_name')
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = ' '.join(_plain_text(value, field_name='El nombre visible', allow_newlines=False).split())
        return normalized or None

    @field_validator('bio')
    @classmethod
    def normalize_bio(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = _plain_text(value, field_name='La biografía', allow_newlines=True)
        return normalized or None


class UserResponse(ApiModel):
    id: int
    username: str
    email: str
    avatar_url: str | None = Field(default=None, serialization_alias='avatarUrl')
    display_name: str | None = Field(default=None, serialization_alias='displayName')
    bio: str | None = None
    created_at: str = Field(serialization_alias='createdAt')
    updated_at: str = Field(serialization_alias='updatedAt')


class AuthResponse(ApiModel):
    user: UserResponse


class MessageResponse(ApiModel):
    message: str


class FavoriteStateResponse(ApiModel):
    content_id: str = Field(serialization_alias='contentId')
    is_favorite: bool = Field(serialization_alias='isFavorite')


class BannerCommentCreateRequest(ApiModel):
    body: str = Field(min_length=1, max_length=1000)

    @field_validator('body')
    @classmethod
    def normalize_body(cls, value: str) -> str:
        normalized = _plain_text(value, field_name='El comentario', allow_newlines=True)
        if not normalized:
            raise ValueError('El comentario no puede estar vacío.')
        return normalized


class BannerCommentAuthorResponse(ApiModel):
    username: str
    display_name: str | None = Field(default=None, serialization_alias='displayName')


class BannerCommentResponse(ApiModel):
    id: int
    banner_id: str = Field(serialization_alias='bannerId')
    body: str
    author: BannerCommentAuthorResponse
    created_at: str = Field(serialization_alias='createdAt')
    is_owner: bool = Field(serialization_alias='isOwner')


class BannerCommentListResponse(ApiModel):
    items: list[BannerCommentResponse]
