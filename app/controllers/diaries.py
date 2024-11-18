from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Path, Query
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload

from app.lib.auth_context import auth_user
from app.lib.locale import INSTALLED_LOCALES_NAMES_MAP, normalize_locale
from app.lib.options_context import options_context
from app.lib.render_response import render_response
from app.lib.translation import primary_translation_locale
from app.limits import (
    DIARY_LIST_PAGE_SIZE,
    DISPLAY_NAME_MAX_LENGTH,
    LOCALE_CODE_MAX_LENGTH,
)
from app.models.db.diary import Diary
from app.models.db.user import User
from app.models.types import DisplayNameType, LocaleCode
from app.queries.diary_query import DiaryQuery
from app.queries.user_query import UserQuery

router = APIRouter()


async def _get_diaries_data(
    *,
    user: User | None,
    language: LocaleCode | None,
    after: int | None,
    before: int | None,
) -> dict:
    primary_locale = primary_translation_locale()
    primary_locale_name = INSTALLED_LOCALES_NAMES_MAP[primary_locale].native
    user_id = user.id if (user is not None) else None
    language = normalize_locale(language) if (language is not None) else None
    if language is not None:
        locale_name = INSTALLED_LOCALES_NAMES_MAP[language]
        language_name = locale_name.native if (language == primary_locale) else locale_name.english
    else:
        language_name = None

    with options_context(
        joinedload(Diary.user).load_only(
            User.id,
            User.display_name,
            User.avatar_type,
            User.avatar_id,
        )
    ):
        diaries = await DiaryQuery.find_many_recent(
            user_id=user_id,
            language=language,
            after=after,
            before=before,
            limit=DIARY_LIST_PAGE_SIZE,
        )

    async def new_after_task():
        after = diaries[0].id
        after_diaries = await DiaryQuery.find_many_recent(
            user_id=user_id,
            language=language,
            after=after,
            limit=1,
        )
        return after if after_diaries else None

    async def new_before_task():
        before = diaries[-1].id
        before_diaries = await DiaryQuery.find_many_recent(
            user_id=user_id,
            language=language,
            before=before,
            limit=1,
        )
        return before if before_diaries else None

    if diaries:
        async with TaskGroup() as tg:
            new_after_t = tg.create_task(new_after_task())
            new_before_t = tg.create_task(new_before_task())
        new_after = new_after_t.result()
        new_before = new_before_t.result()
    else:
        new_after = None
        new_before = None

    base_url = f'/user/{user.display_name}/diary' if (user is not None) else '/diary'
    if language is not None:
        base_url += f'/{language}'

    if language is not None:
        if language == primary_locale:
            active_tab = 1  # viewing own language diaries
        else:
            active_tab = 2  # viewing other language diaries
    elif user is not None:
        current_user = auth_user()
        if (current_user is not None) and user.id == current_user.id:
            active_tab = 3  # viewing own diaries
        else:
            active_tab = 4  # viewing other user's diaries
    else:
        active_tab = 0  # viewing all diaries

    return {
        'profile': user,
        'active_tab': active_tab,
        'primary_locale': primary_locale,
        'primary_locale_name': primary_locale_name,
        'base_url': base_url,
        'language': language,
        'language_name': language_name,
        'new_after': new_after,
        'new_before': new_before,
        'diaries': diaries,
    }


@router.get('/diary')
async def index(
    after: Annotated[PositiveInt | None, Query()] = None,
    before: Annotated[PositiveInt | None, Query()] = None,
):
    data = await _get_diaries_data(user=None, language=None, after=after, before=before)
    return await render_response('diaries/index.jinja2', data)


@router.get('/diary/{language:str}')
async def language(
    language: Annotated[LocaleCode, Path(min_length=1, max_length=LOCALE_CODE_MAX_LENGTH)],
    after: Annotated[PositiveInt | None, Query()] = None,
    before: Annotated[PositiveInt | None, Query()] = None,
):
    data = await _get_diaries_data(user=None, language=language, after=after, before=before)
    return await render_response('diaries/index.jinja2', data)


@router.get('/user/{display_name:str}/diary')
async def personal(
    display_name: Annotated[DisplayNameType, Path(min_length=1, max_length=DISPLAY_NAME_MAX_LENGTH)],
    after: Annotated[PositiveInt | None, Query()] = None,
    before: Annotated[PositiveInt | None, Query()] = None,
):
    user = await UserQuery.find_one_by_display_name(display_name)
    data = await _get_diaries_data(user=user, language=None, after=after, before=before)
    return await render_response('diaries/index.jinja2', data)
