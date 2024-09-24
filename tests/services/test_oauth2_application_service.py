import pytest
from fastapi import HTTPException

from app.lib.translation import translation_context
from app.limits import OAUTH_APP_URI_LIMIT, OAUTH_APP_URI_MAX_LENGTH
from app.models.types import LocaleCode, Uri
from app.services.oauth2_application_service import OAuth2ApplicationService


async def test_validate_redirect_uris_too_many():
    with translation_context(LocaleCode('en')):
        uris = '\nhttps://example.com' * OAUTH_APP_URI_LIMIT
        OAuth2ApplicationService.validate_redirect_uris(uris)

        uris = '\nhttps://example.com' * (OAUTH_APP_URI_LIMIT + 1)
        with pytest.raises(HTTPException):
            OAuth2ApplicationService.validate_redirect_uris(uris)


async def test_validate_redirect_uris_too_long():
    with translation_context(LocaleCode('en')):
        uris = f'https://1.com\n https://{'a' * (OAUTH_APP_URI_MAX_LENGTH - 12)}.com \n'
        OAuth2ApplicationService.validate_redirect_uris(uris)

        uris = f'https://1.com\n https://{'a' * (OAUTH_APP_URI_MAX_LENGTH - 11)}.com \n'
        with pytest.raises(HTTPException):
            OAuth2ApplicationService.validate_redirect_uris(uris)


@pytest.mark.parametrize('uri', ['https:', 'https://', 'uwu'])
async def test_validate_redirect_uris_invalid(uri):
    with translation_context(LocaleCode('en')), pytest.raises(HTTPException):
        OAuth2ApplicationService.validate_redirect_uris(uri)


async def test_validate_redirect_uris_insecure():
    with translation_context(LocaleCode('en')):
        uris = 'http://localhost\nhttp://127.0.0.1'
        OAuth2ApplicationService.validate_redirect_uris(uris)

        uris = 'http://localhost.example.com'
        with pytest.raises(HTTPException):
            OAuth2ApplicationService.validate_redirect_uris(uris)


async def test_validate_redirect_uris_deduplicate():
    uris = 'https://1.com\nhttps://2.com\nhttps://1.com'
    assert OAuth2ApplicationService.validate_redirect_uris(uris) == (
        Uri('https://1.com'),
        Uri('https://2.com'),
    )
