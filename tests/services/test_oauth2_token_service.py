from datetime import timedelta

from zid import zid

from app.config import OAUTH_AUTHORIZATION_CODE_TIMEOUT
from app.db import db
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.types import OAuth2TokenId
from app.services.oauth2_token_service import OAuth2TokenService
from app.services.system_app_service import SYSTEM_APP_CLIENT_ID_MAP


async def test_oauth2_token_cleanup_deletes_only_stale_unauthorized():
    # Arrange: Insert two unauthorized tokens: one stale and one recent
    old_id: OAuth2TokenId = zid()  # type: ignore
    recent_id: OAuth2TokenId = zid()  # type: ignore

    async with db(True) as conn:
        await conn.execute(
            """
            INSERT INTO oauth2_token (
                id, user_id, application_id,
                scopes, created_at
            )
            VALUES
            (
                %(old_id)s, 1, %(app_id)s,
                '{}', statement_timestamp() - %(old_age)s
            ),
            (
                %(recent_id)s, 1, %(app_id)s,
                '{}', statement_timestamp() - %(recent_age)s
            )
            """,
            {
                'old_id': old_id,
                'recent_id': recent_id,
                'app_id': SYSTEM_APP_CLIENT_ID_MAP[SYSTEM_APP_WEB_CLIENT_ID],
                'old_age': OAUTH_AUTHORIZATION_CODE_TIMEOUT + timedelta(minutes=1),
                'recent_age': OAUTH_AUTHORIZATION_CODE_TIMEOUT - timedelta(minutes=1),
            },
        )

    # Act: Trigger cleanup loop
    await OAuth2TokenService.force_process()

    # Assert: Verify only the stale token was deleted
    async with (
        db() as conn,
        await conn.execute(
            'SELECT id FROM oauth2_token WHERE id = ANY(%s)',
            ([old_id, recent_id],),
        ) as r,
    ):
        after_ids: set[OAuth2TokenId] = {row[0] for row in await r.fetchall()}
        assert recent_id in after_ids, 'recent unauthorized token must remain'
        assert old_id not in after_ids, 'stale unauthorized token must be deleted'
