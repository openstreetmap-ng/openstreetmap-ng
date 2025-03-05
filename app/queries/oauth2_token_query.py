from typing import Any

from psycopg.rows import dict_row
from psycopg.sql import SQL

from app.db import db2
from app.lib.crypto import hash_bytes
from app.models.db.oauth2_application import ApplicationId, ClientId
from app.models.db.oauth2_token import OAuth2Token
from app.models.db.user import UserId
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.services.system_app_service import SYSTEM_APP_CLIENT_ID_MAP


class OAuth2TokenQuery:
    @staticmethod
    async def find_one_authorized_by_token(access_token: str) -> OAuth2Token | None:
        """Find an authorized OAuth2 token by token string."""
        access_token_hashed = hash_bytes(access_token)

        async with (
            db2() as conn,
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
    async def find_many_authorized_by_user_app_id(
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
            AND authorized_at IS NOT NULL
            ORDER BY id DESC
            {limit}
        """).format(limit=limit_clause)

        async with db2() as conn, await conn.cursor(row_factory=dict_row).execute(query, params) as r:
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def find_many_authorized_by_user_client_id(
        user_id: UserId,
        client_id: ClientId,
        *,
        limit: int | None = None,
    ) -> list[OAuth2Token]:
        """Find all authorized tokens for the given user and client id."""
        app = await OAuth2ApplicationQuery.find_one_by_client_id(client_id)
        if app is None:
            return []
        return await OAuth2TokenQuery.find_many_authorized_by_user_app_id(user_id, app['id'], limit=limit)

    @staticmethod
    async def find_many_pats_by_user(
        user_id: UserId,
        *,
        limit: int | None = None,
    ) -> list[OAuth2Token]:
        """Find all PAT tokens (authorized or not) for the given user."""
        app_id = SYSTEM_APP_CLIENT_ID_MAP['SystemApp.pat']  # type: ignore
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
            ORDER BY id DESC
            {limit}
        """).format(limit=limit_clause)

        async with db2() as conn, await conn.cursor(row_factory=dict_row).execute(query, params) as r:
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def find_unique_per_app_by_user_id(user_id: UserId) -> list[OAuth2Token]:
        """Find unique OAuth2 tokens per app for the given user."""
        async with (
            db2() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT DISTINCT ON (application_id) * FROM oauth2_token
                WHERE user_id = %s
                AND authorized_at IS NOT NULL
                ORDER BY application_id DESC, id DESC
                """,
                (user_id,),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore
