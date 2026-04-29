from asyncio import TaskGroup
from typing import Annotated

import cython
from fastapi import APIRouter, Path, Query, Response
from feedgen.feed import FeedGenerator
from pydantic import SecretStr
from starlette import status
from starlette.responses import RedirectResponse

from app.config import DIARY_LIST_PAGE_SIZE
from app.format import FormatRSS06
from app.lib.auth_context import auth_user, web_user
from app.lib.locale import LOCALES_NAMES_MAP, normalize_locale
from app.lib.render_response import render_proto_page, render_response
from app.lib.translation import primary_translation_locale, t
from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.middlewares.request_context_middleware import get_request
from app.models.db.diary import diaries_resolve_rich_text
from app.models.db.user import User, user_proto
from app.models.proto.diary_pb2 import (
    ComposePage,
    DetailsPage,
    IndexPage,
    UserCommentsPage,
)
from app.models.proto.shared_pb2 import LonLat
from app.models.types import DiaryId, LocaleCode, UserId
from app.queries.diary_comment_query import DiaryCommentQuery
from app.queries.diary_query import DiaryQuery
from app.queries.user_query import UserQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.rpc.diary import _build_entry
from app.services.user_token_unsubscribe_service import UserTokenUnsubscribeService
from app.validators.display_name import DisplayNameNormalizing

router = APIRouter()


@router.get('/diary/new')
async def new():
    return await render_proto_page(
        ComposePage(),
        title_prefix=t('diary.new_entry').capitalize(),
    )


@router.get('/diary/{diary_id:int}')
async def details(
    diary_id: DiaryId,
    *,
    unsubscribe: bool = False,
):
    diary = await DiaryQuery.find_by_id(diary_id)
    if diary is None:
        return await render_response(
            'diary/not-found',
            {'diary_id': diary_id},
            status=status.HTTP_404_NOT_FOUND,
        )

    async with TaskGroup() as tg:
        diaries = [diary]
        tg.create_task(UserQuery.resolve_users(diaries))
        tg.create_task(diaries_resolve_rich_text(diaries))
        tg.create_task(DiaryQuery.resolve_location_name(diaries))
        tg.create_task(DiaryCommentQuery.resolve_num_comments(diaries))
        tg.create_task(UserSubscriptionQuery.resolve_is_subscribed('diary', diaries))

    profile = diary['user']  # type: ignore

    return await render_proto_page(
        DetailsPage(entry=_build_entry(diary)),
        title_prefix=(
            f'{t("diary_entries.index.user_title", user=profile["display_name"])}'
            f' | {diary["title"]}'
        ),
        template_data={
            'unsubscribe_target': 'diary' if unsubscribe else None,
            'unsubscribe_id': diary_id if unsubscribe else None,
        },
    )


@router.get('/diary/{diary_id:int}/unsubscribe')
async def get_unsubscribe(
    _: Annotated[User, web_user()],
    diary_id: DiaryId,
):
    if not await UserSubscriptionQuery.is_subscribed('diary', diary_id):
        return RedirectResponse(f'/diary/{diary_id}', status.HTTP_303_SEE_OTHER)
    return await details(diary_id, unsubscribe=True)


@router.post('/diary/{diary_id:int}/unsubscribe')
async def post_unsubscribe(
    diary_id: DiaryId,
    token: Annotated[SecretStr, Query(min_length=1)],
):
    token_struct = await UserTokenStructUtils.from_str_stateless(token)
    await UserTokenUnsubscribeService.unsubscribe('diary', diary_id, token_struct)
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.get('/diary/{diary_id:int}/subscription')
async def legacy_subscription(diary_id: DiaryId):
    return RedirectResponse(f'/diary/{diary_id}/unsubscribe')


@router.get('/diary/{diary_id:int}/edit')
async def edit(
    user: Annotated[User, web_user()],
    diary_id: DiaryId,
):
    diary = await DiaryQuery.find_by_id(diary_id)
    if diary is None or diary['user_id'] != user['id']:
        return await render_response(
            'diary/not-found',
            {'diary_id': diary_id},
            status=status.HTTP_404_NOT_FOUND,
        )

    point = diary['point']
    return await render_proto_page(
        ComposePage(
            diary_id=diary_id,
            title=diary['title'],
            body=diary['body'],
            language=diary['language'],
            location=LonLat(lon=point.x, lat=point.y) if point is not None else None,
        ),
        title_prefix=t('diary_entries.edit.title').capitalize(),
    )


@router.get('/diary')
async def index():
    page = IndexPage()
    return await render_proto_page(
        page,
        title_prefix=_build_heading(page),
    )


@router.get('/diary/rss')
async def index_rss():
    return await _get_rss_feed(IndexPage())


@router.get('/diary/{language:str}/rss')
async def language_index_rss(
    language: Annotated[LocaleCode, Path(min_length=1)],
):
    normalized_language = normalize_locale(language)
    if normalized_language is None:
        return Response(None, status.HTTP_404_NOT_FOUND)

    return await _get_rss_feed(
        IndexPage(language=normalized_language),
        language=normalized_language,
    )


@router.get('/diary/{language:str}')
async def language_index(
    language: Annotated[LocaleCode, Path(min_length=1)],
):
    normalized_language = normalize_locale(language)
    if normalized_language is None:
        return Response(None, status.HTTP_404_NOT_FOUND)

    page = IndexPage(language=normalized_language)
    return await render_proto_page(
        page,
        title_prefix=_build_heading(page),
    )


@router.get('/user/{display_name:str}/diary')
async def user_index(
    display_name: Annotated[DisplayNameNormalizing, Path(min_length=1)],
):
    user = await UserQuery.find_by_display_name(display_name)
    if user is None:
        return await render_response(
            'user/profile/not-found',
            {'name': display_name},
            status=status.HTTP_404_NOT_FOUND,
        )
    current_user = auth_user()
    page = (
        IndexPage(self=IndexPage.Self())
        if current_user is not None and user['id'] == current_user['id']
        else IndexPage(profile=user_proto(user))
    )
    return await render_proto_page(
        page,
        title_prefix=_build_heading(page),
    )


@router.get('/user/{display_name:str}/diary/rss')
async def user_index_rss(
    display_name: Annotated[DisplayNameNormalizing, Path(min_length=1)],
):
    user = await UserQuery.find_by_display_name(display_name)
    if user is None:
        return Response(None, status.HTTP_404_NOT_FOUND)

    current_user = auth_user()
    page = (
        IndexPage(self=IndexPage.Self())
        if current_user is not None and user['id'] == current_user['id']
        else IndexPage(profile=user_proto(user))
    )
    return await _get_rss_feed(page, user_id=user['id'])


@router.get('/user/{display_name:str}/diary/comments')
async def user_comments(
    display_name: Annotated[DisplayNameNormalizing, Path(min_length=1)],
):
    user = await UserQuery.find_by_display_name(display_name)
    if user is None:
        return await render_response(
            'user/profile/not-found',
            {'name': display_name},
            status=status.HTTP_404_NOT_FOUND,
        )

    return await render_proto_page(
        UserCommentsPage(user=user_proto(user)),
        title_prefix=t('diary_entries.comments.heading', user=user['display_name']),
    )


@router.get('/user/{_:str}/diary/{diary_id:int}{suffix:path}')
async def legacy_user_diary(_, diary_id: DiaryId, suffix: str):
    return RedirectResponse(
        f'/diary/{diary_id}{suffix}', status.HTTP_301_MOVED_PERMANENTLY
    )


@cython.cfunc
def _build_heading(
    page: IndexPage,
):
    if page.HasField('language'):
        language = normalize_locale(LocaleCode(page.language))
        assert language is not None
        if language == primary_translation_locale():
            return t(
                'diary_entries.index.in_language_title',
                language=LOCALES_NAMES_MAP[primary_translation_locale()].display_name,
            )
        return t(
            'diary_entries.index.in_language_title',
            language=LOCALES_NAMES_MAP[language].display_name,
        )

    if page.HasField('self'):
        return t('diary_entries.index.my_diary')

    if page.HasField('profile'):
        return t(
            'diary_entries.index.user_title',
            user=page.profile.display_name,
        )

    return t('layouts.user_diaries')


async def _get_rss_feed(
    page: IndexPage,
    *,
    user_id: UserId | None = None,
    language: LocaleCode | None = None,
):
    diaries = await DiaryQuery.find_recent(
        user_id=user_id,
        language=language,
        limit=DIARY_LIST_PAGE_SIZE,
    )
    if diaries:
        async with TaskGroup() as tg:
            tg.create_task(UserQuery.resolve_users(diaries))
            tg.create_task(diaries_resolve_rich_text(diaries))

    fg = FeedGenerator()
    fg.language(primary_translation_locale())
    fg.link(href=str(get_request().url), rel='self')
    fg.title(_build_heading(page))
    fg.subtitle(t('diary.index.description'))

    FormatRSS06.encode_diaries(fg, diaries)
    return Response(fg.rss_str(), media_type='application/rss+xml; charset=utf-8')
