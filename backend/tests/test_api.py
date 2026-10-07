from app.schemas import ContentDetailResponse, ContentItemResponse


def test_v16_content_schema_accepts_real_provider_payload() -> None:
    item = ContentItemResponse(
        id='anilist-1', source='anilist', source_attribution='AniList', external_id='1',
        title='Example', original_title='例', category='anime', category_label='Anime', year=2026,
        score=8.5, maturity='NR', format='tv', genres=['Drama'], artwork='https://s4.anilist.co/file/a.jpg',
        studio='Studio', episodes=12, status='airing',
    )
    assert item.category == 'anime'
    detail = ContentDetailResponse(**item.model_dump(), synopsis='Synopsis', origin='JP')
    assert detail.synopsis == 'Synopsis'
