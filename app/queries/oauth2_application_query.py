from psycopg.rows import dict_row

from app.db import db
from app.models.db.oauth2_application import OAuth2Application
from app.models.types import ApplicationId, ClientId, UserId


class OAuth2ApplicationQuery:
    @staticmethod
    async def find_by_id(
        id: ApplicationId, *, user_id: UserId | None = None
    ) -> OAuth2Application | None:
        """Find an OAuth2 application by id."""
        apps = await OAuth2ApplicationQuery.find_by_ids([id])
        app = next(iter(apps), None)
        if app is not None and user_id is not None and app['user_id'] != user_id:
            return None
        return app

    @staticmethod
    async def find_by_ids(ids: list[ApplicationId]) -> list[OAuth2Application]:
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
    async def find_by_client_id(client_id: ClientId) -> OAuth2Application | None:
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
    async def find_by_user(user_id: UserId) -> list[OAuth2Application]:
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
        items: list,
        *,
        application_id_key: str = 'application_id',
        application_key: str = 'application',
    ) -> list[OAuth2Application]:
        """Resolve application fields for the given items."""
        if not items:
            return []

        id_map: dict[ApplicationId, list] = {}
        for item in items:
            application_id: ApplicationId | None = item.get(application_id_key)
            if application_id is None:
                continue
            list_ = id_map.get(application_id)
            if list_ is None:
                id_map[application_id] = [item]
            else:
                list_.append(item)

        if not id_map:
            return []

        apps = await OAuth2ApplicationQuery.find_by_ids(list(id_map))
        for app in apps:
            for item in id_map[app['id']]:
                item[application_key] = app

        return apps
