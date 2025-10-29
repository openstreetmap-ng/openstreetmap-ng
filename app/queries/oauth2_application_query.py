from datetime import datetime
from typing import Any, Literal

from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable

from app.config import ADMIN_APPLICATION_LIST_PAGE_SIZE
from app.db import db
from app.lib.standard_pagination import standard_pagination_range
from app.models.db.oauth2_application import OAuth2Application
from app.models.types import ApplicationId, ClientId, DisplayName, UserId
from app.queries.user_query import UserQuery


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

    @staticmethod
    async def find(
        mode: Literal['count', 'ids', 'page'],
        /,
        *,
        page: int | None = None,
        num_items: int | None = None,
        search: str | None = None,
        owner: str | None = None,
        interacted_user: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        sort: Literal['created_asc', 'created_desc'] = 'created_desc',
        limit: int | None = None,
    ) -> int | list[OAuth2Application] | list[ApplicationId]:
        conditions: list[Composable] = []
        params: list[Any] = []

        if search:
            ors: list[Composable] = [SQL('name ILIKE %s'), SQL('client_id = %s')]
            params.extend((f'%{search}%', search))

            if search.isdigit():
                ors.append(SQL('id = %s'))
                params.append(int(search))

            conditions.append(SQL('({})').format(SQL(' OR ').join(ors)))

        if owner:
            owner_ids: list[UserId] = []

            # Try to parse as user ID
            try:
                owner_ids.append(UserId(int(owner)))
            except (ValueError, TypeError):
                pass

            # Try to find by display name
            user_by_name = await UserQuery.find_by_display_name(DisplayName(owner))
            if user_by_name is not None:
                owner_ids.append(user_by_name['id'])

            if not owner_ids:
                # No matching user found, return empty results
                if mode == 'count':
                    return 0
                return []

            conditions.append(SQL('user_id = ANY(%s)'))
            params.append(owner_ids)

        if interacted_user:
            interactor_ids: list[UserId] = []

            # Try to parse as user ID
            try:
                interactor_ids.append(UserId(int(interacted_user)))
            except (ValueError, TypeError):
                pass

            # Try to find by display name
            user_by_name = await UserQuery.find_by_display_name(
                DisplayName(interacted_user)
            )
            if user_by_name is not None:
                interactor_ids.append(user_by_name['id'])

            if not interactor_ids:
                # No matching user found, return empty results
                if mode == 'count':
                    return 0
                return []

            conditions.append(
                SQL(
                    """
                    EXISTS (
                        SELECT 1 FROM oauth2_token
                        WHERE application_id = oauth2_application.id
                        AND user_id = ANY(%s)
                        AND authorized_at IS NOT NULL
                    )
                    """
                )
            )
            params.append(interactor_ids)

        if created_after:
            conditions.append(SQL('created_at >= %s'))
            params.append(created_after)

        if created_before:
            conditions.append(SQL('created_at <= %s'))
            params.append(created_before)

        where_clause = SQL(' AND ').join(conditions) if conditions else SQL('TRUE')

        if mode == 'count':
            query = SQL('SELECT COUNT(*) FROM oauth2_application WHERE {}').format(
                where_clause
            )
            async with db() as conn, await conn.execute(query, params) as r:
                return (await r.fetchone())[0]  # type: ignore

        if sort == 'created_desc':
            order_clause = SQL('created_at DESC')
        elif sort == 'created_asc':
            order_clause = SQL('created_at')
        else:
            raise NotImplementedError(f'Unsupported sort {sort!r}')

        if mode == 'ids':
            query = SQL("""
                SELECT id FROM oauth2_application
                WHERE {}
                ORDER BY {}
                LIMIT %s
            """).format(where_clause, order_clause)
            params.append(limit)
            async with db() as conn, await conn.execute(query, params) as r:
                return [row[0] for row in await r.fetchall()]

        # mode == 'page'
        assert page is not None, "Page number must be provided in 'page' mode"
        assert num_items is not None, "Number of items must be provided in 'page' mode"

        stmt_limit, stmt_offset = standard_pagination_range(
            page,
            page_size=ADMIN_APPLICATION_LIST_PAGE_SIZE,
            num_items=num_items,
            reverse=False,  # Page 1 = most recent
        )

        query = SQL("""
            SELECT * FROM oauth2_application
            WHERE {}
            ORDER BY {}
            OFFSET %s
            LIMIT %s
        """).format(where_clause, order_clause)
        params.extend((stmt_offset, stmt_limit))

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            return await r.fetchall()  # type: ignore
