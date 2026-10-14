from app.providers.anilist import map_media


def test_anilist_ova_maps_to_ova_category() -> None:
    item = map_media({
        'id': 10,
        'title': {'romaji': 'OVA'},
        'format': 'OVA',
        'averageScore': 80,
        'coverImage': {'large': 'https://s4.anilist.co/a.jpg'},
    })
    assert item['category'] == 'ova'
    assert item['score'] == 8.0
