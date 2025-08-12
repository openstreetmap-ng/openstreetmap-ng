from collections import defaultdict

from psycopg.rows import dict_row

from app.db import db
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.oauth2_token import OAuth2Token
from app.models.types import ApplicationId, ClientId, UserId


class OAuth2ApplicationQuery:
    @staticmethod
    async def find_one_by_id(
        id: ApplicationId, *, user_id: UserId | None = None
    ) -> OAuth2Application | None:
        """Find an OAuth2 application by id."""
        apps = await OAuth2ApplicationQuery.find_many_by_ids([id])
        app = next(iter(apps), None)
        if app is not None and user_id is not None and app['user_id'] != user_id:
            return None
        return app

    @staticmethod
    async def find_many_by_ids(ids: list[ApplicationId]) -> list[OAuth2Application]:
        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM oauth2_application
                WHERE id = ANY(%s)
                """,
                (ids,),
            ) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def find_one_by_client_id(client_id: ClientId) -> OAuth2Application | None:
        """Find an OAuth2 application by client id."""
        async with (
            db() as conn,
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
    async def find_many_by_user(user_id: UserId) -> list[OAuth2Application]:
        """Get all OAuth2 applications by user id."""
        async with (
            db() as conn,
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

    @staticmethod
    async def resolve_applications(
        tokens: list[OAuth2Token],
    ) -> list[OAuth2Application]:
        """Resolve the applications for the given tokens."""
        if not tokens:
            return []

        id_map: defaultdict[ApplicationId, list[OAuth2Token]] = defaultdict(list)
        for token in tokens:
            id_map[token['application_id']].append(token)

        apps = await OAuth2ApplicationQuery.find_many_by_ids(list(id_map))
        for app in apps:
            for token in id_map[app['id']]:
                token['application'] = app

        return apps
