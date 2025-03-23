import logging
from asyncio import TaskGroup
from datetime import timedelta
from typing import Annotated

from email_validator.rfc_constants import EMAIL_MAX_LENGTH
from fastapi import APIRouter, Cookie, Path, Query, Request
from polyline_rs import encode_lonlat
from pydantic import SecretStr
from starlette import status
from starlette.responses import RedirectResponse

from app.lib.auth_context import auth_user, web_user
from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.lib.render_response import render_response
from app.lib.statistics import user_activity_summary
from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.limits import (
    EMAIL_MIN_LENGTH,
    PASSWORD_MIN_LENGTH,
    URLSAFE_BLACKLIST,
    USER_DESCRIPTION_MAX_LENGTH,
    USER_NEW_DAYS,
    USER_RECENT_ACTIVITY_ENTRIES,
)
from app.models.db.user import User, users_resolve_rich_text
from app.models.types import DisplayName, UserId
from app.queries.changeset_comment_query import ChangesetCommentQuery
from app.queries.changeset_query import ChangesetQuery
from app.queries.diary_comment_query import DiaryCommentQuery
from app.queries.diary_query import DiaryQuery
from app.queries.note_comment_query import NoteCommentQuery
from app.queries.note_query import NoteQuery
from app.queries.trace_query import TraceQuery
from app.queries.user_query import UserQuery
from app.queries.user_token_query import UserTokenQuery
from app.services.auth_provider_service import AuthProviderService

router = APIRouter()


@router.get('/signup')
async def signup(auth_provider_verification: Annotated[str | None, Cookie()] = None):
    if auth_user() is not None:
        return RedirectResponse('/', status.HTTP_303_SEE_OTHER)

    verification = AuthProviderService.validate_verification(auth_provider_verification)
    if verification is not None:
        logging.debug('Signup form contains auth provider verification by %r', verification.provider)
        display_name = verification.name or ''
        email = verification.email or ''
    else:
        display_name = ''
        email = ''

    return await render_response(
        'user/signup.jinja2',
        {
            'display_name_value': display_name,
            'email_value': email,
            'URLSAFE_BLACKLIST': URLSAFE_BLACKLIST,
            'EMAIL_MIN_LENGTH': EMAIL_MIN_LENGTH,
            'EMAIL_MAX_LENGTH': EMAIL_MAX_LENGTH,
            'PASSWORD_MIN_LENGTH': PASSWORD_MIN_LENGTH,
        },
    )


@router.get('/user/new')
async def legacy_signup():
    return RedirectResponse('/signup', status.HTTP_301_MOVED_PERMANENTLY)


@router.get('/user/account-confirm/pending')
async def account_confirm_pending(user: Annotated[User, web_user()]):
    if user['email_verified']:
        return RedirectResponse('/welcome', status.HTTP_303_SEE_OTHER)

    return await render_response('user/account_confirm_pending.jinja2')


@router.get('/reset-password')
async def reset_password(token: Annotated[SecretStr | None, Query(min_length=1)] = None):
    if token is None:
        return await render_response('user/reset_password.jinja2')

    # TODO: check errors
    token_struct = UserTokenStructUtils.from_str(token)

    user_token = await UserTokenQuery.find_one_by_token_struct('reset_password', token_struct, check_email_hash=False)
    if user_token is None:
        return await render_response('user/reset_password.jinja2')

    await UserQuery.resolve_users([user_token])

    return await render_response(
        'user/reset_password_token.jinja2',
        {
            'token': token.get_secret_value(),
            'profile': user_token['user'],  # pyright: ignore [reportTypedDictNotRequiredAccess]
            'PASSWORD_MIN_LENGTH': PASSWORD_MIN_LENGTH,
        },
    )


@router.get('/user/forgot-password')
async def legacy_forgot_password():
    return RedirectResponse('/reset-password', status.HTTP_301_MOVED_PERMANENTLY)


@router.get('/user/reset-password')
async def legacy_reset_password(token: Annotated[SecretStr, Query(min_length=1)]):
    return RedirectResponse(f'/reset-password?token={token.get_secret_value()}', status.HTTP_301_MOVED_PERMANENTLY)


@router.get('/user-id/{user_id:int}{suffix:path}')
async def permalink(
    request: Request,
    user_id: UserId,
    suffix: str,
):
    user = await UserQuery.find_one_by_id(user_id)
    if user is None:
        raise_for.user_not_found(user_id)

    location = f'/user/{user["display_name"]}{suffix}'
    if query := request.url.query:
        location += f'?{query}'

    return RedirectResponse(location, status.HTTP_307_TEMPORARY_REDIRECT)


@router.get('/user/{display_name:str}')
async def index(
    display_name: Annotated[DisplayName, Path(min_length=1)],
):
    user = await UserQuery.find_one_by_display_name(display_name)
    if user is None:
        return await render_response(
            'user/profile/not_found.jinja2',
            {'name': display_name},
            status=status.HTTP_404_NOT_FOUND,
        )
    user_id = user['id']

    current_user = auth_user()
    is_self = current_user is not None and current_user['id'] == user_id
    account_age = utcnow() - user['created_at']
    is_new_user = account_age < timedelta(days=USER_NEW_DAYS)

    async def changesets_task():
        changesets = await ChangesetQuery.find_many_by_query(
            user_ids=[user_id],
            sort='desc',
            limit=USER_RECENT_ACTIVITY_ENTRIES,
        )
        await ChangesetCommentQuery.resolve_num_comments(changesets)
        return changesets

    async def notes_task(tg: TaskGroup):
        notes = await NoteQuery.find_many_by_query(
            user_id=user_id,
            event='opened',
            sort_by='updated_at',
            sort_dir='desc',
            limit=USER_RECENT_ACTIVITY_ENTRIES,
        )
        tg.create_task(NoteCommentQuery.resolve_comments(notes, per_note_sort='asc', per_note_limit=1))
        tg.create_task(NoteCommentQuery.resolve_num_comments(notes))
        return notes

    async def traces_task():
        traces = await TraceQuery.find_many_recent(
            user_id=user_id,
            limit=USER_RECENT_ACTIVITY_ENTRIES,
        )
        await TraceQuery.resolve_coords(traces, limit_per_trace=100, resolution=90)
        return traces

    async def diaries_task():
        diaries = await DiaryQuery.find_many_recent(
            user_id=user_id,
            limit=USER_RECENT_ACTIVITY_ENTRIES,
        )
        await DiaryCommentQuery.resolve_num_comments(diaries)
        return diaries

    async with TaskGroup() as tg:
        tg.create_task(users_resolve_rich_text([user]))
        activity_t = tg.create_task(user_activity_summary(user_id))
        changesets_t = tg.create_task(changesets_task())
        changesets_count_t = tg.create_task(ChangesetQuery.count_by_user_id(user_id))
        # TODO: changesets_comments_count_t = ...
        notes_t = tg.create_task(notes_task(tg))
        notes_count_t = tg.create_task(NoteQuery.count_by_user_id(user_id))
        notes_comments_count_t = tg.create_task(NoteQuery.count_by_user_id(user_id, commented_other=True))
        traces_t = tg.create_task(traces_task())
        traces_count_t = tg.create_task(TraceQuery.count_by_user_id(user_id))
        diaries_t = tg.create_task(diaries_task())
        diaries_count_t = tg.create_task(DiaryQuery.count_by_user_id(user_id))
        diaries_comments_count_t = tg.create_task(DiaryCommentQuery.count_by_user_id(user_id))

    activity_data = activity_t.result()

    changesets = changesets_t.result()
    changesets_count = changesets_count_t.result()
    changesets_comments_count = 0  # TODO: changesets_comments_count_t.result()

    notes = notes_t.result()
    notes_count = notes_count_t.result()
    notes_comments_count = notes_comments_count_t.result()

    traces = traces_t.result()
    traces_lines = ';'.join(encode_lonlat(trace['coords'].tolist(), 0) for trace in traces)  # type: ignore
    traces_count = traces_count_t.result()

    diaries = diaries_t.result()
    diaries_count = diaries_count_t.result()
    diaries_comments_count = diaries_comments_count_t.result()

    # TODO: groups
    groups_count = 0
    groups = ()

    return await render_response(
        'user/profile/index.jinja2',
        {
            'profile': user,
            'is_self': is_self,
            'is_new_user': is_new_user,
            'changesets_count': changesets_count,
            'changesets_comments_count': changesets_comments_count,
            'changesets': changesets,
            'notes_count': notes_count,
            'notes_comments_count': notes_comments_count,
            'notes': notes,
            'traces_count': traces_count,
            'traces': traces,
            'traces_lines': traces_lines,
            'diaries_count': diaries_count,
            'diaries_comments_count': diaries_comments_count,
            'diaries': diaries,
            'groups_count': groups_count,
            'groups': groups,
            'USER_DESCRIPTION_MAX_LENGTH': USER_DESCRIPTION_MAX_LENGTH,
            'USER_RECENT_ACTIVITY_ENTRIES': USER_RECENT_ACTIVITY_ENTRIES,
            **activity_data,
        },
    )
