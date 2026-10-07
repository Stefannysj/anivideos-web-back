import pytest
from pydantic import ValidationError
from app.schemas import BannerCommentCreateRequest


def test_comment_normalization_and_limit() -> None:
    assert BannerCommentCreateRequest(body='  Hola  ').body == 'Hola'
    with pytest.raises(ValidationError):
        BannerCommentCreateRequest(body='x' * 1001)
