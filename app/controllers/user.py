from datetime import UTC, datetime, timedelta
from typing import Annotated

import numpy as np
from anyio import create_task_group
from fastapi import APIRouter, Path
from starlette import status
from starlette.responses import RedirectResponse

from app.lib.auth_context import auth_user, web_user
from app.lib.date_utils import utcnow
from app.lib.legal import legal_terms
from app.lib.render_response import render_response
from app.limits import DISPLAY_NAME_MAX_LENGTH, USER_NEW_DAYS, USER_RECENT_ACTIVITY_ENTRIES
from app.models.db.user import User
from app.models.note_event import NoteEvent
from app.models.user_status import UserStatus
from app.queries.changeset_comment_query import ChangesetCommentQuery
from app.queries.changeset_query import ChangesetQuery
from app.queries.note_comment_query import NoteCommentQuery
from app.queries.note_query import NoteQuery
from app.queries.trace_query import TraceQuery
from app.queries.trace_segment_query import TraceSegmentQuery
from app.queries.user_query import UserQuery
from app.utils import JSON_ENCODE

router = APIRouter(prefix='/user')

ACTIVITY_CHART_LENGTH = 365


@router.get('/terms')
async def terms(user: Annotated[User, web_user()]):
    if user.status != UserStatus.pending_terms:
        return RedirectResponse('/', status.HTTP_303_SEE_OTHER)
    return render_response(
        'user/terms.jinja2',
        {
            'legal_terms_GB': legal_terms('GB'),
            'legal_terms_FR': legal_terms('FR'),
            'legal_terms_IT': legal_terms('IT'),
        },
    )


@router.get('/account-confirm/pending')
async def account_confirm_pending(user: Annotated[User, web_user()]):
    if user.status != UserStatus.pending_activation:
        return RedirectResponse('/welcome', status.HTTP_303_SEE_OTHER)
    return render_response('user/account_confirm_pending.jinja2')


@router.get('/new')
async def legacy_signup():
    return RedirectResponse('/signup', status.HTTP_301_MOVED_PERMANENTLY)


# TODO: optimize
@router.get('/{display_name:str}')
async def index(display_name: Annotated[str, Path(min_length=1, max_length=DISPLAY_NAME_MAX_LENGTH)]):
    user = await UserQuery.find_one_by_display_name(display_name)

    if user is None:
        res = render_response('user/profile/not_found.jinja2', {'name': display_name})
        res.status_code = status.HTTP_404_NOT_FOUND
        return res

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

    async with create_task_group() as tg:
        for note in notes:
            tg.start_soon(note.comments[0].resolve_rich_text)

    traces_count = await TraceQuery.count_by_user_id(user.id)
    traces = await TraceQuery.find_many_by_user_id(
        user.id,
        sort='desc',
        limit=USER_RECENT_ACTIVITY_ENTRIES,
    )
    await TraceSegmentQuery.resolve_coords(traces, limit_per_trace=100, resolution=100)
    traces_coords = JSON_ENCODE(tuple(trace.coords for trace in traces)).decode()

    # TODO: diaries
    diaries_count = 0
    diaries = ()

    # TODO: groups
    groups_count = 0
    groups = ()

    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    created_since = today - timedelta(days=ACTIVITY_CHART_LENGTH - 1)

    changesets_count_per_day = await ChangesetQuery.count_per_day_by_user_id(user.id, created_since)
    dates_range = np.arange(
        created_since,
        today + timedelta(days=1),
        timedelta(days=1),
        dtype=datetime,
    )
    activity = np.array(
        [changesets_count_per_day.get(date.replace(tzinfo=UTC), 0) for date in dates_range], dtype=float
    )
    perc = max(np.percentile(activity, 95), 1)
    activity = np.clip(activity / perc, 0, 1) * 19
    activity = np.round(activity).astype(int)
    return render_response(
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
            'traces_coords': traces_coords,
            'diaries_count': diaries_count,
            'diaries': diaries,
            'groups_count': groups_count,
            'groups': groups,
            'USER_RECENT_ACTIVITY_ENTRIES': USER_RECENT_ACTIVITY_ENTRIES,
            'activity': activity,
        },
    )
