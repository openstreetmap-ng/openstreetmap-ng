from asyncio import TaskGroup
from typing import override

import cython
from connectrpc.request import RequestContext
from fastapi import HTTPException
from psycopg.sql import SQL
from shapely import Point
from starlette import status

from app.config import DIARY_COMMENTS_PAGE_SIZE, DIARY_LIST_PAGE_SIZE
from app.lib.auth_context import require_web_user
from app.lib.locale import normalize_locale
from app.lib.standard_pagination import sp_paginate_table
from app.models.db.diary import Diary, diaries_resolve_rich_text
from app.models.db.diary_comment import DiaryComment, diary_comments_resolve_rich_text
from app.models.db.user import user_proto
from app.models.proto.diary_connect import Service, ServiceASGIApplication
from app.models.proto.diary_pb2 import (
    AddCommentRequest,
    AddCommentResponse,
    Comment,
    CreateOrUpdateRequest,
    CreateOrUpdateResponse,
    DeleteRequest,
    DeleteResponse,
    Entry,
    GetCommentsRequest,
    GetCommentsResponse,
    GetPageRequest,
    GetPageResponse,
    GetUserCommentsPageRequest,
    GetUserCommentsPageResponse,
    UpdateSubscriptionRequest,
    UpdateSubscriptionResponse,
)
from app.models.proto.shared_pb2 import LonLat
from app.models.types import DiaryId, LocaleCode, UserId
from app.queries.diary_comment_query import DiaryCommentQuery
from app.queries.diary_query import DiaryQuery
from app.queries.user_query import UserQuery
from app.services.diary_comment_service import DiaryCommentService
from app.services.diary_service import DiaryService
from app.services.user_subscription_service import UserSubscriptionService


class _Service(Service):
    @override
    async def get_page(self, request: GetPageRequest, ctx: RequestContext):
        if request.HasField('user_id'):
            user_id = UserId(request.user_id)
            where = SQL('user_id = %s')
            params: tuple[object, ...] = (user_id,)
        elif request.HasField('language'):
            language = normalize_locale(LocaleCode(request.language))
            if language is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Invalid language')
            where = SQL('language = %s')
            params = (language,)
        else:
            where = SQL('TRUE')
            params = ()

        diaries, state = await sp_paginate_table(
            Diary,
            request.state.SerializeToString(),
            table='diary',
            where=where,
            params=params,
            page_size=DIARY_LIST_PAGE_SIZE,
            cursor_column='id',
            cursor_kind='id',
            order_dir='desc',
        )

        async with TaskGroup() as tg:
            tg.create_task(UserQuery.resolve_users(diaries))
            tg.create_task(diaries_resolve_rich_text(diaries))
            tg.create_task(DiaryQuery.resolve_location_name(diaries))
            tg.create_task(DiaryCommentQuery.resolve_num_comments(diaries))

        return GetPageResponse(
            state=state,
            diaries=[_build_entry(diary) for diary in diaries],
        )

    @override
    async def get_comments(
        self,
        request: GetCommentsRequest,
        ctx: RequestContext,
    ):
        diary_id = DiaryId(request.diary_id)

        comments, state = await sp_paginate_table(
            DiaryComment,
            request.state.SerializeToString(),
            table='diary_comment',
            where=SQL('diary_id = %s'),
            params=(diary_id,),
            page_size=DIARY_COMMENTS_PAGE_SIZE,
            order_dir='desc',
            display_dir='asc',
        )

        async with TaskGroup() as tg:
            tg.create_task(UserQuery.resolve_users(comments))
            tg.create_task(diary_comments_resolve_rich_text(comments))

        return GetCommentsResponse(
            state=state,
            comments=[_build_comment(comment) for comment in comments],
        )

    @override
    async def get_user_comments_page(
        self,
        request: GetUserCommentsPageRequest,
        ctx: RequestContext,
    ):
        user_id = UserId(request.user_id)

        comments, state = await sp_paginate_table(
            DiaryComment,
            request.state.SerializeToString(),
            table='diary_comment',
            where=SQL('user_id = %s'),
            params=(user_id,),
            page_size=DIARY_COMMENTS_PAGE_SIZE,
            cursor_column='id',
            cursor_kind='id',
            order_dir='desc',
        )

        async with TaskGroup() as tg:
            tg.create_task(DiaryQuery.resolve_diary(comments))
            tg.create_task(diary_comments_resolve_rich_text(comments))

        return GetUserCommentsPageResponse(
            state=state,
            entries=_user_comments_entries(comments),
        )

    @override
    async def create_or_update(
        self,
        request: CreateOrUpdateRequest,
        ctx: RequestContext,
    ):
        require_web_user()
        point = _resolve_point(request)

        if request.HasField('diary_id'):
            diary_id = DiaryId(request.diary_id)
            await DiaryService.update(
                diary_id=diary_id,
                title=request.title,
                body=request.body,
                language=LocaleCode(request.language),
                point=point,
            )
        else:
            diary_id = await DiaryService.create(
                title=request.title,
                body=request.body,
                language=LocaleCode(request.language),
                point=point,
            )

        return CreateOrUpdateResponse(id=diary_id)

    @override
    async def delete(self, request: DeleteRequest, ctx: RequestContext):
        require_web_user()
        await DiaryService.delete(DiaryId(request.diary_id))
        return DeleteResponse()

    @override
    async def update_subscription(
        self,
        request: UpdateSubscriptionRequest,
        ctx: RequestContext,
    ):
        require_web_user()

        diary_id = DiaryId(request.diary_id)
        if request.is_subscribed:
            await UserSubscriptionService.subscribe('diary', diary_id)
        else:
            await UserSubscriptionService.unsubscribe('diary', diary_id)

        return UpdateSubscriptionResponse()

    @override
    async def add_comment(
        self,
        request: AddCommentRequest,
        ctx: RequestContext,
    ):
        require_web_user()
        await DiaryCommentService.comment(DiaryId(request.diary_id), request.body)
        return AddCommentResponse()


service = _Service()
asgi_app_cls = ServiceASGIApplication


@cython.cfunc
def _resolve_point(request: CreateOrUpdateRequest):
    return (
        Point(request.location.lon, request.location.lat)
        if request.HasField('location')
        else None
    )


@cython.cfunc
def _user_comments_entries(comments: list[DiaryComment]):
    return [
        GetUserCommentsPageResponse.Entry(
            id=comment['id'],
            created_at=int(comment['created_at'].timestamp()),
            diary_id=comment['diary_id'],
            diary_title=comment['diary']['title'],  # type: ignore
            body_rich=comment['body_rich'],  # type: ignore
        )
        for comment in comments
    ]


def _build_entry(diary: Diary):
    point = diary['point']
    location = None
    if point is not None:
        location = LonLat(lon=point.x, lat=point.y)

    return Entry(
        id=diary['id'],
        user=user_proto(diary['user']),  # type: ignore
        title=diary['title'],
        created_at=int(diary['created_at'].timestamp()),
        updated_at=int(diary['updated_at'].timestamp()),
        language=diary['language'],
        body_rich=diary['body_rich'],  # type: ignore
        location_name=diary.get('location_name'),
        location=location,
        num_comments=diary['num_comments'],  # type: ignore
        is_subscribed='is_subscribed' in diary,
    )


@cython.cfunc
def _build_comment(comment: DiaryComment):
    return Comment(
        id=comment['id'],
        user=user_proto(comment['user']),  # type: ignore
        created_at=int(comment['created_at'].timestamp()),
        body_rich=comment['body_rich'],  # type: ignore
    )
