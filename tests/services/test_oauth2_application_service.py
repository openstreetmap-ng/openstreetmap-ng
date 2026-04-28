import pytest
from fastapi import HTTPException
from PIL import DecompressionBombError
from starlette import status

from app.config import OAUTH_APP_URI_LIMIT, OAUTH_APP_URI_MAX_LENGTH
from app.lib.locale import DEFAULT_LOCALE
from app.lib.translation import translation_context
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.services.oauth2_application_service import OAuth2ApplicationService


@pytest.mark.parametrize(
    ('uris', 'expected'),
    [
        # Count limits
        ('\nhttps://example.com' * OAUTH_APP_URI_LIMIT, ['https://example.com']),
        ('\nhttps://example.com' * (OAUTH_APP_URI_LIMIT + 1), None),
        # Length limits
        (
            f'https://1.com\n https://{"a" * (OAUTH_APP_URI_MAX_LENGTH - 12)}.com \n',
            ['https://1.com', f'https://{"a" * (OAUTH_APP_URI_MAX_LENGTH - 12)}.com'],
        ),
        (
            f'https://1.com\n https://{"a" * (OAUTH_APP_URI_MAX_LENGTH - 11)}.com \n',
            None,
        ),
        # OOB URIs
        ('urn:ietf:wg:oauth:2.0:oob', ['urn:ietf:wg:oauth:2.0:oob']),
        ('urn:ietf:wg:oauth:2.0:oob:auto', ['urn:ietf:wg:oauth:2.0:oob:auto']),
        # Invalid URIs
        ('https:', None),
        ('https://', None),
        ('uwu', None),
        # Allow loopback HTTP
        (
            'http://localhost:3000/callback\nhttp://127.0.0.1:8000/callback',
            ['http://localhost:3000/callback', 'http://127.0.0.1:8000/callback'],
        ),
        ('http://[::1]:9000/callback', ['http://[::1]:9000/callback']),
        (
            'http://localhost\nhttp://127.0.0.1',
            ['http://localhost', 'http://127.0.0.1'],
        ),
        # Insecure URIs
        ('http://localhost.example.com', None),
        # Duplicate URIs
        (
            'https://1.com\nhttps://2.com\nhttps://1.com',
            ['https://1.com', 'https://2.com'],
        ),
        ('https://1.com\nhttps://2.com', ['https://1.com', 'https://2.com']),
    ],
)
def test_validate_redirect_uris(uris, expected):
    with translation_context(DEFAULT_LOCALE):
        try:
            result = OAuth2ApplicationService.validate_redirect_uris(uris)
            assert expected is not None, 'Expected validation to fail, but it succeeded'
            assert sorted(result) == sorted(expected)
        except HTTPException:
            assert expected is None, 'Expected validation to succeed, but it failed'


async def test_update_avatar_decompression_bomb(monkeypatch):
    async def fail_upload_avatar(*args, **kwargs):
        raise DecompressionBombError('too big')

    monkeypatch.setattr(
        'app.services.oauth2_application_service.ImageService.upload_avatar', fail_upload_avatar
    )

    with translation_context(DEFAULT_LOCALE):
        with pytest.raises(HTTPException) as exc_info:
            await OAuth2ApplicationService.update_avatar(
                SYSTEM_APP_WEB_CLIENT_ID,
                avatar_file=None,  # type: ignore[arg-type]
            )

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc_info.value.detail[0]['msg'] == 'Image file is too big'
