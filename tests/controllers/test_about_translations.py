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
async def test_about_invalid_locale(client: AsyncClient, locale):
    client.headers['Authorization'] = 'User user1'
    r = await client.get(f'/about/{locale}')
    assert r.status_code == status.HTTP_404_NOT_FOUND, r.text


async def test_about_user_with_default_locale(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # Test default about page (no explicit locale)
    r = await client.get('/about')
    assert r.is_success, r.text
    with translation_context(LocaleCode('en')):
        assert t('site.about.community_driven_title') in r.text

    # Test about page with explicit English locale
    r = await client.get('/about/en')
    assert r.is_success, r.text
    with translation_context(LocaleCode('en')):
        assert t('site.about.community_driven_title') in r.text

    # Test about page with explicit Polish locale
    r = await client.get('/about/pl')
    assert r.is_success, r.text
    with translation_context(LocaleCode('pl')):
        assert t('site.about.community_driven_title') in r.text


async def test_about_user_with_polish_locale(client: AsyncClient):
    # Create a user with Polish locale preference
    with auth_context(None):
        await TestService.create_user(DisplayName('polish'), language=LocaleCode('pl'))
    client.headers['Authorization'] = 'User polish'

    # Test default about page (no explicit locale)
    r = await client.get('/about')
    assert r.is_success, r.text
    with translation_context(LocaleCode('pl')):
        assert t('site.about.community_driven_title') in r.text

    # Test about page with explicit English locale
    r = await client.get('/about/en')
    assert r.is_success, r.text
    with translation_context(LocaleCode('en')):
        assert t('site.about.community_driven_title') in r.text

    # Test about page with explicit Polish locale
    r = await client.get('/about/pl')
    assert r.is_success, r.text
    with translation_context(LocaleCode('pl')):
        assert t('site.about.community_driven_title') in r.text
