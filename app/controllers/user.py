from datetime import UTC, datetime, timedelta
from itertools import cycle
from typing import Annotated

import numpy as np
from email_validator.rfc_constants import EMAIL_MAX_LENGTH
from fastapi import APIRouter, Path, Request
from polyline_rs import encode_lonlat
from pydantic import PositiveInt
from starlette import status
from starlette.responses import RedirectResponse

from app.lib.auth_context import auth_user, web_user
from app.lib.date_utils import format_short_date, get_month_name, get_weekday_name, utcnow
from app.lib.exceptions_context import raise_for
from app.lib.legal import legal_terms
from app.lib.render_response import render_response
from app.limits import (
    DISPLAY_NAME_MAX_LENGTH,
    EMAIL_MIN_LENGTH,
    PASSWORD_MIN_LENGTH,
    URLSAFE_BLACKLIST,
    USER_ACTIVITY_CHART_WEEKS,
    USER_DESCRIPTION_MAX_LENGTH,
    USER_NEW_DAYS,
    USER_RECENT_ACTIVITY_ENTRIES,
)
from app.models.db.note_comment import NoteEvent
from app.models.db.user import User, UserStatus
from app.models.types import DisplayNameType
from app.queries.changeset_comment_query import ChangesetCommentQuery
from app.queries.changeset_query import ChangesetQuery
from app.queries.note_comment_query import NoteCommentQuery
from app.queries.note_query import NoteQuery
from app.queries.trace_query import TraceQuery
from app.queries.trace_segment_query import TraceSegmentQuery
from app.queries.user_query import UserQuery

router = APIRouter()


@router.get('/user/permalink/{user_id:int}{path:path}')
async def permalink(
    request: Request,
    user_id: Annotated[PositiveInt, Path()],
    path: Annotated[str | None, Path()],
):
    user = await UserQuery.find_one_by_id(user_id)
    if user is None:
        raise_for().user_not_found(user_id)
    location = f'/user/{user.display_name}{path}'
    if query := request.url.query:
        location += f'?{query}'
    return RedirectResponse(location, status.HTTP_302_FOUND)


# TODO: optimize
@router.get('/user/{display_name:str}')
async def index(
    display_name: Annotated[DisplayNameType, Path(min_length=1, max_length=DISPLAY_NAME_MAX_LENGTH)],
):
    user = await UserQuery.find_one_by_display_name(display_name)

    if user is None:
        response = await render_response('user/profile/not_found.jinja2', {'name': display_name})
        response.status_code = status.HTTP_404_NOT_FOUND
        return response

    await user.resolve_rich_text()

    me = auth_user()
    is_self = (me is not None) and me.id == user.id

    account_age = utcnow() - user.created_at
    is_new_user = account_age < timedelta(days=USER_NEW_DAYS)

    changesets_count = await ChangesetQuery.count_by_user_id(user.id)
    changeset_comments_count = 0  # TODO:
    changesets = await ChangesetQuery.find_many_by_query(
        user_id=user.id,
        sort='desc',
        limit=USER_RECENT_ACTIVITY_ENTRIES,
    )
    await ChangesetCommentQuery.resolve_num_comments(changesets)

    notes_count = await NoteQuery.count_by_user_id(user.id)
    note_comments_count = 0  # TODO:
    notes = await NoteQuery.find_many_by_query(
        user_id=user.id,
        event=NoteEvent.opened,
        sort_dir='desc',
        limit=USER_RECENT_ACTIVITY_ENTRIES,
    )
    await NoteCommentQuery.resolve_comments(notes, per_note_sort='asc', per_note_limit=1)

    traces_count = await TraceQuery.count_by_user_id(user.id)
    traces = await TraceQuery.find_many_by_user_id(
        user.id,
        sort='desc',
        limit=USER_RECENT_ACTIVITY_ENTRIES,
    )
    await TraceSegmentQuery.resolve_coords(traces, limit_per_trace=100, resolution=90)
    traces_lines = ';'.join(encode_lonlat(trace.coords.tolist(), 0) for trace in traces)

    # TODO: diaries
    diaries_count = 0
    diaries = ()

    # TODO: groups
    groups_count = 0
    groups = ()

    activity_data = await _get_activity_data(user)

    return await render_response(
        'user/profile/index.jinja2',
        {
            'profile': user,
            'is_self': is_self,
            'is_new_user': is_new_user,
            'changesets_count': changesets_count,
            'changeset_comments_count': changeset_comments_count,
            'changesets': changesets,
            'notes_count': notes_count,
            'note_comments_count': note_comments_count,
            'notes': notes,
            'traces_count': traces_count,
            'traces': traces,
            'traces_lines': traces_lines,
            'diaries_count': diaries_count,
            'diaries': diaries,
            'groups_count': groups_count,
            'groups': groups,
            'USER_DESCRIPTION_MAX_LENGTH': USER_DESCRIPTION_MAX_LENGTH,
            'USER_RECENT_ACTIVITY_ENTRIES': USER_RECENT_ACTIVITY_ENTRIES,
            **activity_data,
        },
    )


async def _get_activity_data(user: User) -> dict:
    """
    Get activity data for the given user.

    It is used to render the activity chart on the user pages.
    """
    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    weekday = (today.weekday() + 1) % 7  # put sunday on top
    created_since = today - timedelta(days=USER_ACTIVITY_CHART_WEEKS * 7 + weekday)
    changesets_count_per_day = await ChangesetQuery.count_per_day_by_user_id(user.id, created_since)
    dates_range = np.arange(
        created_since,
        today + timedelta(days=1),
        timedelta(days=1),
        dtype=datetime,
    )
    activity = np.array(
        tuple(changesets_count_per_day.get(date.replace(tzinfo=UTC), 0) for date in dates_range),
        dtype=np.uint64,
    )
    activity_positive = activity[activity > 0]
    max_activity_clip = np.percentile(activity_positive, 95) if activity_positive.size else 1
    activity_level_perc = np.clip(activity / max_activity_clip, 0, 1)
    activity_levels = np.ceil(activity_level_perc * 19).astype(np.uint8)

    weekdays = tuple(
        get_weekday_name(date, short=True)
        if i % 2 == 1  #
        else ''
        for i, date in enumerate(dates_range[:7])
    )
    months: list[str | None] = []
    rows: tuple[list[dict], ...] = tuple([] for _ in range(7))

    for week_data, level, value, date in zip(cycle(rows), activity_levels, activity, dates_range):
        week_data.append({'level': level, 'value': value, 'date': format_short_date(date)})
        if date.day == 1:  # month change
            months.extend(None for _ in range(len(week_data) - len(months)))
            months.append(get_month_name(date, short=True))

    return {
        'activity_months': months,
        'activity_weekdays': weekdays,
        'activity_rows': rows,
        'activity_max': activity.max(),
        'activity_sum': activity.sum(),  # total activities
        'activity_days': (activity > 0).sum(),  # total mapping days
    }


@router.get('/user/new')
async def legacy_signup():
    return RedirectResponse('/signup', status.HTTP_301_MOVED_PERMANENTLY)


@router.get('/signup')
async def signup():
    if auth_user() is not None:
        return RedirectResponse('/', status.HTTP_303_SEE_OTHER)
    return await render_response(
        'user/signup.jinja2',
        {
            'URLSAFE_BLACKLIST': URLSAFE_BLACKLIST,
            'EMAIL_MIN_LENGTH': EMAIL_MIN_LENGTH,
            'EMAIL_MAX_LENGTH': EMAIL_MAX_LENGTH,
            'PASSWORD_MIN_LENGTH': PASSWORD_MIN_LENGTH,
        },
    )


@router.get('/user/account-confirm/pending')
async def account_confirm_pending(user: Annotated[User, web_user()]):
    if user.status != UserStatus.pending_activation:
        return RedirectResponse('/welcome', status.HTTP_303_SEE_OTHER)
    return await render_response('user/account_confirm_pending.jinja2')


@router.get('/user/terms')
async def terms(user: Annotated[User, web_user()]):
    if user.status != UserStatus.pending_terms:
        return RedirectResponse('/', status.HTTP_303_SEE_OTHER)
    return await render_response(
        'user/terms.jinja2',
        {
            'legal_terms_GB': legal_terms('GB'),
            'legal_terms_FR': legal_terms('FR'),
            'legal_terms_IT': legal_terms('IT'),
        },
    )


@router.get('/user/forgot-password')
async def legacy_reset_password():
    return RedirectResponse('/reset-password', status.HTTP_301_MOVED_PERMANENTLY)


@router.get('/reset-password')
async def reset_password():
    return await render_response('user/reset_password.jinja2')
