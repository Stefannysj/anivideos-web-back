from app.schemas import PlatformLinkResponse


def test_provider_links_have_small_stable_contract() -> None:
    link = PlatformLinkResponse(name='Official', url='https://example.com')
    assert link.model_dump() == {'name':'Official','url':'https://example.com','attribution':None}
