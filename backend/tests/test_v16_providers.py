from app.providers.anilist import map_media
from app.providers.tmdb import map_details


def test_anilist_ova_maps_to_ova_category() -> None:
    item = map_media({'id':10,'title':{'romaji':'OVA'},'format':'OVA','averageScore':80,'coverImage':{'large':'https://s4.anilist.co/a.jpg'}})
    assert item['category'] == 'ova'
    assert item['score'] == 8.0


def test_tmdb_kdrama_mapping() -> None:
    item = map_details({'id':20,'name':'Drama','original_name':'드라마','first_air_date':'2026-01-01','poster_path':'/a.jpg','vote_average':7.4,'genres':[{'name':'Drama'}],'status':'Returning Series','videos':{'results':[]},'watch/providers':{'results':{}}}, category='k-drama', media_type='tv', region='PE')
    assert item['category'] == 'k-drama'
    assert item['status'] == 'airing'
