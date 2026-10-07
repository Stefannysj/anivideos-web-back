from app.schemas import FavoriteStateResponse


def test_favorite_contract_is_backward_compatible() -> None:
    value = FavoriteStateResponse(content_id='anilist-1', is_favorite=True)
    assert value.model_dump(by_alias=True) == {'contentId':'anilist-1','isFavorite':True}
