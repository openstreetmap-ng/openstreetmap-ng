from typing import Any, NotRequired, get_origin

from psycopg.rows import dict_row
from psycopg.sql import SQL, Identifier
from pydantic import SecretStr

from app.db import db
from app.lib.crypto import hash_bytes
from app.models.db.oauth2_application import SYSTEM_APP_PAT_CLIENT_ID
from app.models.db.oauth2_token import OAuth2Token
from app.models.db.user import User
from app.models.types import ApplicationId, ClientId, UserId
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.services.system_app_service import SYSTEM_APP_CLIENT_ID_MAP

_USER_COLS_TO_ALIAS: dict[str, str] = {
    k: f'user__{k}'
    for k, t in User.__annotations__.items()
    if get_origin(t) is not NotRequired
}
_USER_COLS = SQL(',').join(
    SQL('"user".{} AS {}').format(Identifier(k), Identifier(alias))
    for k, alias in _USER_COLS_TO_ALIAS.items()
)


class OAuth2TokenQuery:
    @staticmethod
    async def find_authorized_by_token(
        access_token: SecretStr,
    ) -> OAuth2Token | None:
        """Find an authorized OAuth2 token by token string."""
        access_token_hashed = hash_bytes(access_token.get_secret_value())

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM oauth2_token
                WHERE token_hashed = %s
                AND authorized_at IS NOT NULL
                """,
                (access_token_hashed,),
            ) as r,
        ):
            return await r.fetchone()  # type: ignore

    @staticmethod
    async def find_authorized_by_token_with_user(
        access_token: SecretStr,
    ) -> OAuth2Token | None:
        """Find an authorized OAuth2 token and its user in one query.

        Uses a simple JOIN and prefixes user columns as user__* to avoid collisions,
        then reconstructs the user dict and removes the prefixed keys.
        This preserves DB type adapters (e.g., geometry → shapely).
        """
        access_token_hashed = hash_bytes(access_token.get_secret_value())

        query = SQL(
            """
            SELECT t.*, {}
            FROM oauth2_token t
            JOIN "user" ON "user".id = t.user_id
            WHERE t.token_hashed = %s
            AND t.authorized_at IS NOT NULL
            """
        ).format(_USER_COLS)

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                query, (access_token_hashed,)
            ) as r,
        ):
            row = await r.fetchone()
            if row is None:
                return None

        token: OAuth2Token = row  # type: ignore
        token['user'] = {k: row.pop(alias) for k, alias in _USER_COLS_TO_ALIAS.items()}  # type: ignore
        return token

    @staticmethod
    async def find_authorized_by_user_app_id(
        user_id: UserId,
        app_id: ApplicationId,
        *,
        limit: int | None = None,
    ) -> list[OAuth2Token]:
        """Find all authorized OAuth2 tokens for the given user and app id."""
        params: list[Any] = [user_id, app_id]

        if limit is not None:
            limit_clause = SQL('LIMIT %s')
            params.append(limit)
        else:
            limit_clause = SQL('')

        query = SQL("""
            SELECT * FROM oauth2_token
            WHERE user_id = %s
            AND application_id = %s
            AND NOT unlisted
            AND authorized_at IS NOT NULL
            ORDER BY id DESC
            {limit}
        """).format(limit=limit_clause)

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def find_authorized_by_user_client_id(
        user_id: UserId,
        client_id: ClientId,
        *,
        limit: int | None = None,
    ) -> list[OAuth2Token]:
        """Find all authorized tokens for the given user and client id."""
        app = await OAuth2ApplicationQuery.find_by_client_id(client_id)
        if app is None:
            return []
        return await OAuth2TokenQuery.find_authorized_by_user_app_id(
            user_id, app['id'], limit=limit
        )

    @staticmethod
    async def find_pats_by_user(
        user_id: UserId,
        *,
        limit: int | None = None,
    ) -> list[OAuth2Token]:
        """Find all PAT tokens (authorized or not) for the given user."""
        app_id = SYSTEM_APP_CLIENT_ID_MAP[SYSTEM_APP_PAT_CLIENT_ID]
        params: list[Any] = [user_id, app_id]

        if limit is not None:
            limit_clause = SQL('LIMIT %s')
            params.append(limit)
        else:
            limit_clause = SQL('')

        query = SQL("""
            SELECT * FROM oauth2_token
            WHERE user_id = %s
            AND application_id = %s
            AND NOT unlisted
            ORDER BY id DESC
            {limit}
        """).format(limit=limit_clause)

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def find_unique_per_app_by_user(user_id: UserId) -> list[OAuth2Token]:
        """Find unique OAuth2 tokens per app for the given user."""
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT DISTINCT ON (application_id) * FROM oauth2_token
                WHERE user_id = %s
                AND NOT unlisted
                AND authorized_at IS NOT NULL
                ORDER BY application_id DESC, id DESC
                """,
                (user_id,),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def count_users_by_applications(
        app_ids: list[ApplicationId],
    ) -> dict[ApplicationId, int]:
        """Count distinct authorized users per application."""
        if not app_ids:
            return {}
        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT application_id, COUNT(DISTINCT user_id)
                FROM oauth2_token
                WHERE application_id = ANY(%s)
                AND authorized_at IS NOT NULL
                GROUP BY application_id
                """,
                (app_ids,),
            ) as r,
        ):
            rows: list[tuple[ApplicationId, int]] = await r.fetchall()
        return dict(rows)
