import pytest
from httpx import AsyncClient
from starlette import status

from app.lib.auth_context import auth_context
from app.lib.translation import t, translation_context
from app.models.types import DisplayName, LocaleCode
from app.services.test_service import TestService


@pytest.mark.parametrize(
    'locale',
    [
        'invalid',
        'xx',
        '123',
    ],
)
async def test_copyright_invalid_locale(client: AsyncClient, locale):
    r = await client.get(f'/copyright/{locale}')
    assert r.status_code == status.HTTP_404_NOT_FOUND, r.text


async def test_copyright_user_with_default_locale(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    r = await client.get('/copyright')
    assert r.is_success, r.text

    with translation_context(LocaleCode('en')):
        assert t('site.copyright.foreign.title') not in r.text
        assert t('site.about.legal_1_1_openstreetmap_foundation') in r.text

    # Test copyright page with explicit English locale
    r = await client.get('/copyright/en')
    assert r.is_success, r.text

    with translation_context(LocaleCode('en')):
        # Same expectations as default page
        assert t('site.copyright.foreign.title') not in r.text
        assert t('site.about.legal_1_1_openstreetmap_foundation') in r.text

    # Test copyright page with explicit Polish locale
    r = await client.get('/copyright/pl')
    assert r.is_success, r.text

    with translation_context(LocaleCode('en')):
        # When viewing non-default locale, should see foreign locale notice
        assert t('site.copyright.foreign.title') in r.text

    with translation_context(LocaleCode('pl')):
        # Page content should be in Polish
        assert t('site.about.legal_1_1_openstreetmap_foundation') in r.text


async def test_copyright_user_with_polish_locale(client: AsyncClient):
    # Create a user with Polish locale preference
    with auth_context(None, ()):
        await TestService.create_user(DisplayName('polish'), language=LocaleCode('pl'))
    client.headers['Authorization'] = 'User polish'

    r = await client.get('/copyright')
    assert r.is_success, r.text

    with translation_context(LocaleCode('pl')):
        # For default page, content should be in user's preferred locale
        assert t('site.copyright.foreign.title') in r.text
        assert t('site.about.legal_1_1_openstreetmap_foundation') in r.text

    # Test copyright page with explicit English locale
    r = await client.get('/copyright/en')
    assert r.is_success, r.text

    with translation_context(LocaleCode('pl')):
        # For non-preferred locale, should show foreign locale notice
        assert t('site.copyright.foreign.title') in r.text

    with translation_context(LocaleCode('en')):
        # Content should be in requested locale (English)
        assert t('site.about.legal_1_1_openstreetmap_foundation') in r.text

    # Test copyright page with explicit Polish locale
    r = await client.get('/copyright/pl')
    assert r.is_success, r.text

    with translation_context(LocaleCode('pl')):
        # Both foreign notice (since user is Polish) and content should be in Polish
        assert t('site.copyright.foreign.title') in r.text
        assert t('site.about.legal_1_1_openstreetmap_foundation') in r.text
