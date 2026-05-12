import pytest
from httpx import AsyncClient
from starlette import status

from app.lib.auth_context import auth_context
from app.lib.translation import t, translation_context
from app.models.types import DisplayName, LocaleCode
from app.services.test_service import TestService


@pytest.mark.parametrize('locale', ['invalid', 'xx', '123'])
async def test_copyright_invalid_locale(client: AsyncClient, locale):
    r = await client.get(f'/copyright/{locale}')
    assert r.status_code == status.HTTP_404_NOT_FOUND, r.text


async def test_copyright_title_locale_matches_url(client: AsyncClient):
    """The server-rendered <title> uses the URL's locale (or primary when bare)."""
    with auth_context(None):
        await TestService.create_user(DisplayName('polish'), language=LocaleCode('pl'))

    client.headers['Authorization'] = 'User user1'  # primary=en
    with translation_context(LocaleCode('en')):
        en_title = t('layouts.copyright')
    with translation_context(LocaleCode('pl')):
        pl_title = t('layouts.copyright')

    # /copyright (bare) — primary=en → English title
    r = await client.get('/copyright')
    assert r.is_success, r.text
    assert en_title in r.text

    # /copyright/pl — explicit Polish title
    r = await client.get('/copyright/pl')
    assert r.is_success, r.text
    assert pl_title in r.text

    # As Polish-primary user, /copyright (bare) → Polish title
    client.headers['Authorization'] = 'User polish'
    r = await client.get('/copyright')
    assert r.is_success, r.text
    assert pl_title in r.text

    # /copyright/en still renders English title for the same user
    r = await client.get('/copyright/en')
    assert r.is_success, r.text
    assert en_title in r.text
