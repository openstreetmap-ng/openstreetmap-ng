from asyncio import TaskGroup
from string.templatelib import Template
from typing import override

import cython
from connectrpc.request import RequestContext
from fastapi import HTTPException
from shapely import Point
from starlette import status

from app.config import DIARY_COMMENTS_PAGE_SIZE, DIARY_LIST_PAGE_SIZE
from app.lib.auth.context import require_web_user
from app.lib.standard.pagination import sp_paginate_table
from app.lib.text.locale import normalize_locale
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
)
from app.models.proto.shared_pb2 import StandardPaginationRequest
from app.models.types import DiaryId, LocaleCode, UserId
from app.queries.diary_query import DiaryCommentQuery, DiaryQuery
from app.queries.user_query import UserQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.diary_service import DiaryCommentService, DiaryService


class _Service(Service):
    @override
    async def get_page(self, request: GetPageRequest, ctx: RequestContext):
        where: Template
        if request.HasField('user_id'):
            user_id = UserId(request.user_id)
            where = t'user_id = {user_id}'
        elif request.HasField('language'):
            language = normalize_locale(LocaleCode(request.language))
            if language is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Invalid language')
            where = t'language = {language}'
        else:
            where = t'TRUE'

        diaries, state = await sp_paginate_table(
            Diary,
            request.state,
            table='diary',
            where=where,
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

        response = GetPageResponse()
        response.state.CopyFrom(state)
        for diary in diaries:
            build_entry(response.diaries.add(), diary)
        return response

    @override
    async def get_comments(
        self,
        request: GetCommentsRequest,
        ctx: RequestContext,
    ):
        return await _build_get_comments_response(
            request.state, DiaryId(request.diary_id)
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
            request.state,
            table='diary_comment',
            where=t'user_id = {user_id}',
            page_size=DIARY_COMMENTS_PAGE_SIZE,
            cursor_column='id',
            cursor_kind='id',
            order_dir='desc',
        )

        async with TaskGroup() as tg:
            tg.create_task(DiaryQuery.resolve_diary(comments))
            tg.create_task(diary_comments_resolve_rich_text(comments))

        response = GetUserCommentsPageResponse()
        response.state.CopyFrom(state)
        _add_user_comments_entries(response, comments)
        return response

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
    async def add_comment(
        self,
        request: AddCommentRequest,
        ctx: RequestContext,
    ):
        require_web_user()
        diary_id = DiaryId(request.diary_id)
        await DiaryCommentService.comment(diary_id, request.body)
        # Refresh entry + first comments page in parallel so the response carries
        # fresh state and the client can update in-place (no remount/refetch).
        async with TaskGroup() as tg:
            entry_task = tg.create_task(_build_entry_for_id(diary_id))
            comments_task = tg.create_task(
                _build_get_comments_response(StandardPaginationRequest(), diary_id)
            )
        return AddCommentResponse(
            entry=entry_task.result(),
            comments=comments_task.result(),
        )


service = _Service()
asgi_app_cls = ServiceASGIApplication


async def _build_get_comments_response(
    state_request: StandardPaginationRequest, diary_id: DiaryId
):
    comments, state = await sp_paginate_table(
        DiaryComment,
        state_request,
        table='diary_comment',
        where=t'diary_id = {diary_id}',
        page_size=DIARY_COMMENTS_PAGE_SIZE,
        order_dir='desc',
        display_dir='asc',
    )

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(comments))
        tg.create_task(diary_comments_resolve_rich_text(comments))

    response = GetCommentsResponse()
    response.state.CopyFrom(state)
    for comment in comments:
        _build_comment(response.comments.add(), comment)
    return response


async def _build_entry_for_id(diary_id: DiaryId):
    diary = await DiaryQuery.find_by_id(diary_id)
    if diary is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Diary not found')
    async with TaskGroup() as tg:
        diaries = [diary]
        tg.create_task(UserQuery.resolve_users(diaries))
        tg.create_task(diaries_resolve_rich_text(diaries))
        tg.create_task(DiaryQuery.resolve_location_name(diaries))
        tg.create_task(DiaryCommentQuery.resolve_num_comments(diaries))
        tg.create_task(UserSubscriptionQuery.resolve_is_subscribed('diary', diaries))
    entry = Entry()
    build_entry(entry, diary)
    return entry


@cython.cfunc
def _resolve_point(request: CreateOrUpdateRequest):
    return (
        Point(request.location.lon, request.location.lat)
        if request.HasField('location')
        else None
    )


@cython.cfunc
def _add_user_comments_entries(
    response: GetUserCommentsPageResponse,
    comments: list[DiaryComment],
):
    for comment in comments:
        entry = response.entries.add()
        entry.id = comment['id']
        entry.created_at = int(comment['created_at'].timestamp())
        entry.diary_id = comment['diary_id']
        entry.diary_title = comment['diary']['title']  # type: ignore
        entry.body_rich = comment['body_rich']  # type: ignore


def build_entry(result: Entry, diary: Diary):
    point = diary['point']
    result.id = diary['id']
    result.user.CopyFrom(user_proto(diary['user']))  # type: ignore
    result.title = diary['title']
    result.created_at = int(diary['created_at'].timestamp())
    result.updated_at = int(diary['updated_at'].timestamp())
    result.language = diary['language']
    result.body_rich = diary['body_rich']  # type: ignore
    if point is not None:
        result.location.coords.lon = point.x
        result.location.coords.lat = point.y
        if (location_name := diary.get('location_name')) is not None:
            result.location.name = location_name
    result.num_comments = diary['num_comments']  # type: ignore
    result.is_subscribed = 'is_subscribed' in diary


@cython.cfunc
def _build_comment(result: Comment, comment: DiaryComment):
    result.id = comment['id']
    result.user.CopyFrom(user_proto(comment['user']))  # type: ignore
    result.created_at = int(comment['created_at'].timestamp())
    result.body_rich = comment['body_rich']  # type: ignore
