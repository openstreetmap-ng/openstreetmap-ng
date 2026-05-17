from datetime import datetime
from string.templatelib import Template
from typing import Literal, assert_never

from app.db import db_fetchall, db_fetchcol, db_fetchone, t_and, t_or, t_order
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
        return await db_fetchall(
            OAuth2Application,
            t"""
                SELECT * FROM oauth2_application
                WHERE id = ANY({ids})
            """,
        )

    @staticmethod
    async def find_by_client_id(client_id: ClientId) -> OAuth2Application | None:
        """Find an OAuth2 application by client id."""
        return await db_fetchone(
            OAuth2Application,
            t"""
                SELECT * FROM oauth2_application
                WHERE client_id = {client_id}
            """,
        )

    @staticmethod
    async def find_by_user(user_id: UserId) -> list[OAuth2Application]:
        """Get all OAuth2 applications by user id."""
        return await db_fetchall(
            OAuth2Application,
            t"""
                SELECT * FROM oauth2_application
                WHERE user_id = {user_id}
                ORDER BY id DESC
            """,
        )

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
    async def where_clause(
        *,
        search: str | None = None,
        owner: str | None = None,
        interacted_user: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
    ) -> Template:
        search_cond: Template | None = None
        if search:
            pattern = f'%{search}%'
            ors: list[Template | None] = [
                t'name ILIKE {pattern}',
                t'client_id = {search}',
            ]
            if search.isdigit():
                search_id = int(search)
                ors.append(t'id = {search_id}')
            inner = t_or(*ors)
            search_cond = t'({inner:q})'

        owner_cond: Template | None = None
        if owner:
            owner_ids: list[UserId] = []

            # Try to parse as user ID
            try:
                owner_ids.append(UserId(int(owner)))
            except ValueError, TypeError:
                pass

            # Try to find by display name
            user_by_name = await UserQuery.find_by_display_name(DisplayName(owner))
            if user_by_name is not None:
                owner_ids.append(user_by_name['id'])

            if not owner_ids:
                return t'FALSE'

            owner_cond = t'user_id = ANY({owner_ids})'

        interacted_cond: Template | None = None
        if interacted_user:
            interactor_ids: list[UserId] = []

            # Try to parse as user ID
            try:
                interactor_ids.append(UserId(int(interacted_user)))
            except ValueError, TypeError:
                pass

            # Try to find by display name
            user_by_name = await UserQuery.find_by_display_name(
                DisplayName(interacted_user)
            )
            if user_by_name is not None:
                interactor_ids.append(user_by_name['id'])

            if not interactor_ids:
                return t'FALSE'

            interacted_cond = t"""
                EXISTS (
                    SELECT 1 FROM oauth2_token
                    WHERE application_id = oauth2_application.id
                    AND user_id = ANY({interactor_ids})
                    AND authorized_at IS NOT NULL
                )
            """

        return t_and(
            search_cond,
            owner_cond,
            interacted_cond,
            t'created_at >= {created_after}' if created_after else None,
            t'created_at <= {created_before}' if created_before else None,
        )

    @staticmethod
    async def find_ids(
        *,
        limit: int,
        search: str | None = None,
        owner: str | None = None,
        interacted_user: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        sort: Literal['created_asc', 'created_desc'] = 'created_desc',
    ) -> list[ApplicationId]:
        where = await OAuth2ApplicationQuery.where_clause(
            search=search,
            owner=owner,
            interacted_user=interacted_user,
            created_after=created_after,
            created_before=created_before,
        )

        if sort == 'created_desc':
            order_dir = t_order('desc')
        elif sort == 'created_asc':
            order_dir = t_order('asc')
        else:
            assert_never(sort)

        return await db_fetchcol(
            ApplicationId,
            t"""
                SELECT id FROM oauth2_application
                WHERE {where:q}
                ORDER BY created_at {order_dir:q}, id {order_dir:q}
                LIMIT {limit}
            """,
        )
