from typing import Any

from psycopg.rows import dict_row
from psycopg.sql import SQL

from app.db import db2
from app.models.db.oauth2_application import ApplicationId, ClientId, OAuth2Application
from app.models.db.user import UserId


class OAuth2ApplicationQuery:
    @staticmethod
    async def find_one_by_id(app_id: ApplicationId, *, user_id: UserId | None = None) -> OAuth2Application | None:
        """Find an OAuth2 application by id."""
        query = SQL("""
            SELECT * FROM oauth2_application
            WHERE id = %s
        """)
        params: list[Any] = [app_id]

        if user_id is not None:
            query = SQL('{} AND user_id = %s').format(query)
            params.append(user_id)

        async with db2() as conn, await conn.cursor(row_factory=dict_row).execute(query, params) as r:
            return await r.fetchone()  # type: ignore

    @staticmethod
    async def find_one_by_client_id(client_id: ClientId) -> OAuth2Application | None:
        """Find an OAuth2 application by client id."""
        async with (
            db2() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM oauth2_application
                WHERE client_id = %s
                """,
                (client_id,),
            ) as r,
        ):
            return await r.fetchone()  # type: ignore

    @staticmethod
    async def get_many_by_user_id(user_id: UserId) -> list[OAuth2Application]:
        """Get all OAuth2 applications by user id."""
        async with (
            db2() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM oauth2_application
                WHERE user_id = %s
                ORDER BY id DESC
                """,
                (user_id,),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore
