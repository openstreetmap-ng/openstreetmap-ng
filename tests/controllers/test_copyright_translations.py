from httpx import AsyncClient
from starlette import status

from app.config import DEFAULT_LANGUAGE
from app.lib.auth_context import auth_context
from app.lib.translation import t, translation_context
from app.services.test_service import TestService


async def test_copyright_wrong_locale(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    locale = 'invalid'
    r = await client.get(f'/copyright/{locale}')
    assert r.status_code == status.HTTP_404_NOT_FOUND


async def test_copyright_user_with_english_locale(client: AsyncClient):
    assert DEFAULT_LANGUAGE == 'en'
    with auth_context(None, ()):
        await TestService.create_user('english', language=DEFAULT_LANGUAGE)
    client.headers['Authorization'] = 'User english'

    r = await client.get(f'/copyright')
    assert r.is_success
    with translation_context('en'):
        assert t('site.copyright.foreign.title') not in r.text
        assert t('site.about.legal_1_1_openstreetmap_foundation') in r.text

    r = await client.get(f'/copyright/en')
    assert r.is_success
    with translation_context('en'):
        assert t('site.copyright.foreign.title') not in r.text
        assert t('site.about.legal_1_1_openstreetmap_foundation') in r.text

    r = await client.get(f'/copyright/pl')
    assert r.is_success
    with translation_context('en'):
        assert t('site.copyright.foreign.title') in r.text
    with translation_context('pl'):
        assert t('site.about.legal_1_1_openstreetmap_foundation') in r.text


async def test_copyright_user_with_polish_locale(client: AsyncClient):
    with auth_context(None, ()):
        await TestService.create_user('polish', language='pl')
    client.headers['Authorization'] = 'User polish'

    r = await client.get(f'/copyright')
    assert r.is_success
    with translation_context('pl'):
        assert t('site.copyright.foreign.title') in r.text
        assert t('site.about.legal_1_1_openstreetmap_foundation') in r.text

    r = await client.get(f'/copyright/en')
    assert r.is_success
    with translation_context('pl'):
        assert t('site.copyright.foreign.title') in r.text
    with translation_context('en'):
        assert t('site.about.legal_1_1_openstreetmap_foundation') in r.text

    r = await client.get(f'/copyright/pl')
    assert r.is_success
    with translation_context('pl'):
        assert t('site.copyright.foreign.title') in r.text
        assert t('site.about.legal_1_1_openstreetmap_foundation') in r.text
