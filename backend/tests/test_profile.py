from app.schemas import ProfileUpdateRequest


def test_profile_plain_text_is_preserved() -> None:
    payload = ProfileUpdateRequest(displayName='  Stefanny  ', bio='Hola')
    assert payload.display_name == 'Stefanny'
