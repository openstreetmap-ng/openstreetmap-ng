from httpx import AsyncClient
from starlette import status

from app.lib.auth_context import auth_context
from app.lib.translation import t, translation_context
from app.services.test_service import TestService


async def test_about_invalid_locale(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    r = await client.get('/about/invalid')
    assert r.status_code == status.HTTP_404_NOT_FOUND


async def test_about_user_with_default_locale(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    r = await client.get('/about')
    assert r.is_success
    with translation_context('en'):
        assert t('site.about.community_driven_title') in r.text

    r = await client.get('/about/en')
    assert r.is_success
    with translation_context('en'):
        assert t('site.about.community_driven_title') in r.text

    r = await client.get('/about/pl')
    assert r.is_success
    with translation_context('pl'):
        assert t('site.about.community_driven_title') in r.text


async def test_about_user_with_polish_locale(client: AsyncClient):
    with auth_context(None, ()):
        await TestService.create_user('polish', language='pl')
    client.headers['Authorization'] = 'User polish'

    r = await client.get('/about')
    assert r.is_success
    with translation_context('pl'):
        assert t('site.about.community_driven_title') in r.text

    r = await client.get('/about/en')
    assert r.is_success
    with translation_context('en'):
        assert t('site.about.community_driven_title') in r.text

    r = await client.get('/about/pl')
    assert r.is_success
    with translation_context('pl'):
        assert t('site.about.community_driven_title') in r.text
