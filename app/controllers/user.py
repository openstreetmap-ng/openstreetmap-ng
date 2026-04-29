import logging
from asyncio import TaskGroup
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, Path, Query, Request
from polyline_rs import encode_lonlat
from pydantic import SecretStr
from starlette import status
from starlette.responses import RedirectResponse

from app.config import PASSWORD_MIN_LENGTH, USER_NEW_DAYS, USER_RECENT_ACTIVITY_ENTRIES
from app.lib.auth_context import auth_user, web_user
from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.lib.image import Image
from app.lib.render_response import render_proto_page, render_response
from app.lib.statistics import user_activity_summary
from app.lib.translation import t
from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.models.db.user import User, user_is_admin, user_is_moderator, user_proto
from app.models.proto.profile_pb2 import Page as ProfilePage
from app.models.proto.settings_connections_pb2 import Provider
from app.models.proto.shared_pb2 import UserSocial
from app.models.proto.signup_pb2 import Page as SignupPage
from app.models.proto.trace_pb2 import Summary
from app.models.types import UserId
from app.queries.changeset_comment_query import ChangesetCommentQuery
from app.queries.changeset_query import ChangesetQuery
from app.queries.diary_comment_query import DiaryCommentQuery
from app.queries.diary_query import DiaryQuery
from app.queries.note_comment_query import NoteCommentQuery
from app.queries.note_query import NoteQuery
from app.queries.trace_query import TraceQuery
from app.queries.user_follow_query import UserFollowQuery
from app.queries.user_profile_query import UserProfileQuery
from app.queries.user_query import UserQuery
from app.queries.user_token_query import UserTokenQuery
from app.services.auth_provider_service import AuthProviderService
from app.validators.display_name import DisplayNameNormalizing

router = APIRouter()


@router.get('/signup')
async def signup(auth_provider_verification: Annotated[str | None, Cookie()] = None):
    if auth_user() is not None:
        return RedirectResponse('/', status.HTTP_303_SEE_OTHER)

    verification = AuthProviderService.validate_verification(auth_provider_verification)
    if verification is not None:
        logging.debug(
            'Signup form contains auth provider verification by %r',
            Provider.Name(verification.identity.provider),
        )
        page = SignupPage(verification=verification.identity)
    else:
        page = SignupPage()

    return await render_proto_page(
        page,
        title_prefix=t('layouts.sign_up').capitalize(),
    )


@router.get('/user/new')
async def legacy_signup():
    return RedirectResponse('/signup', status.HTTP_301_MOVED_PERMANENTLY)


@router.get('/user/account-confirm/pending')
async def account_confirm_pending(user: Annotated[User, web_user()]):
    if user['email_verified']:
        return RedirectResponse('/welcome', status.HTTP_303_SEE_OTHER)

    return await render_response('user/account-confirm')


@router.get('/reset-password')
async def reset_password(
    token: Annotated[SecretStr | None, Query(min_length=1)] = None,
):
    if token is None:
        return await render_response('user/reset-password')

    # TODO: check errors
    token_struct = UserTokenStructUtils.from_str(token)

    user_token = await UserTokenQuery.find_by_token_struct(
        'reset_password', token_struct, check_email_hash=False
    )
    if user_token is None:
        return await render_response('user/reset-password')

    await UserQuery.resolve_users([user_token])

    return await render_response(
        'user/reset-password-token',
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
    return RedirectResponse(
        f'/reset-password?token={token.get_secret_value()}',
        status.HTTP_301_MOVED_PERMANENTLY,
    )


@router.get('/user-id/{user_id:int}{suffix:path}')
async def permalink(
    request: Request,
    user_id: UserId,
    suffix: str,
):
    user = await UserQuery.find_by_id(user_id)
    if user is None:
        raise_for.user_not_found(user_id)

    location = f'/user/{user["display_name"]}{suffix}'
    if query := request.url.query:
        location += f'?{query}'

    return RedirectResponse(location)


@router.get('/user/{display_name:str}')
async def index(display_name: Annotated[DisplayNameNormalizing, Path(min_length=1)]):
    user = await UserQuery.find_by_display_name(display_name)
    if user is None:
        return await render_response(
            'user/profile/not-found',
            {'name': display_name},
            status=status.HTTP_404_NOT_FOUND,
        )
    user_id = user['id']

    current_user = auth_user()
    is_self = current_user is not None and current_user['id'] == user_id
    account_age = utcnow() - user['created_at']
    is_new_user = account_age < timedelta(days=USER_NEW_DAYS)

    async def changesets_task():
        changesets = await ChangesetQuery.find(
            user_ids=[user_id],
            sort='desc',
            limit=USER_RECENT_ACTIVITY_ENTRIES,
        )
        await ChangesetCommentQuery.resolve_num_comments(changesets)
        return changesets

    async def notes_task(tg: TaskGroup):
        notes = await NoteQuery.find(
            user_id=user_id,
            event='opened',
            sort_by='updated_at',
            sort_dir='desc',
            limit=USER_RECENT_ACTIVITY_ENTRIES,
        )
        tg.create_task(
            NoteCommentQuery.resolve_comments(
                notes, per_note_sort='asc', per_note_limit=1
            )
        )
        tg.create_task(NoteCommentQuery.resolve_num_comments(notes))
        return notes

    async def traces_task():
        traces = await TraceQuery.find_recent(
            user_id=user_id,
            limit=USER_RECENT_ACTIVITY_ENTRIES,
        )
        await TraceQuery.resolve_coords(traces, limit_per_trace=100, resolution=90)
        return traces

    async def diaries_task():
        diaries = await DiaryQuery.find_recent(
            user_id=user_id,
            limit=USER_RECENT_ACTIVITY_ENTRIES,
        )
        await DiaryCommentQuery.resolve_num_comments(diaries)
        return diaries

    async with TaskGroup() as tg:
        user_profile_t = tg.create_task(UserProfileQuery.get_by_user_id(user_id))
        activity_t = tg.create_task(user_activity_summary(user_id))
        changesets_t = tg.create_task(changesets_task())
        changesets_count_t = tg.create_task(ChangesetQuery.count_by_user(user_id))
        changesets_comments_count_t = tg.create_task(
            ChangesetCommentQuery.count_by_user(user_id)
        )
        notes_t = tg.create_task(notes_task(tg))
        notes_count_t = tg.create_task(NoteQuery.count_by_user(user_id))
        notes_comments_count_t = tg.create_task(
            NoteQuery.count_by_user(user_id, commented_other=True)
        )
        traces_t = tg.create_task(traces_task())
        traces_count_t = tg.create_task(TraceQuery.count_by_user(user_id))
        diaries_t = tg.create_task(diaries_task())
        diaries_count_t = tg.create_task(DiaryQuery.count_by_user(user_id))
        diaries_comments_count_t = tg.create_task(
            DiaryCommentQuery.count_by_user(user_id)
        )

        # Check follow status if viewing another user's profile
        follow_status_t = (
            tg.create_task(UserFollowQuery.get_follow_status(user_id))
            if (not is_self and current_user is not None)
            else None
        )

    changesets_comments_count = changesets_comments_count_t.result()

    traces = traces_t.result()

    # TODO: groups
    groups_count = 0

    user_profile = user_profile_t.result()

    # Get follow status results
    if follow_status_t is not None:
        follow_status = follow_status_t.result()
        is_following = follow_status.is_following
        is_followed_by = follow_status.is_followed_by
    else:
        is_following = False
        is_followed_by = False

    profile_page_state = ProfilePage(
        user=user_proto(user),
        is_new_user=is_new_user,
        is_administrator=user_is_admin(user),
        is_moderator=user_is_moderator(user),
        background_url=Image.get_background_url(user['background_id']),
        created_at=int(user['created_at'].timestamp()),
        chart=activity_t.result(),
        follow=(
            ProfilePage.FollowState(
                target_user_id=user_id,
                is_following=is_following,
                is_followed_by=is_followed_by,
            )
            if follow_status_t is not None
            else None
        ),
        description=user_profile['description'],
        description_rich=user_profile['description_rich'],  # type: ignore
        socials=[
            UserSocial(service=s.service, value=s.value)
            for s in user_profile['socials']
        ],
        changesets_count=changesets_count_t.result(),
        changesets_comments_count=changesets_comments_count,
        changesets=[
            ProfilePage.ChangesetSummary(
                id=changeset['id'],
                created_at=int(changeset['created_at'].timestamp()),
                comment=changeset['tags'].get('comment'),
                num_comments=changeset['num_comments'],  # type: ignore
                num_create=changeset['num_create'],
                num_modify=changeset['num_modify'],
                num_delete=changeset['num_delete'],
            )
            for changeset in changesets_t.result()
        ],
        notes_count=notes_count_t.result(),
        notes_comments_count=notes_comments_count_t.result(),
        notes=[
            ProfilePage.NoteSummary(
                id=note['id'],
                created_at=int(note['created_at'].timestamp()),
                updated_at=int(note['updated_at'].timestamp()),
                is_closed=note['closed_at'] is not None,
                body=note['comments'][0]['body'],  # type: ignore
                num_comments=note['num_comments'],  # type: ignore
            )
            for note in notes_t.result()
        ],
        traces_count=traces_count_t.result(),
        traces=[
            Summary(
                id=trace['id'],
                created_at=int(trace['created_at'].timestamp()),
                description=trace['description'],
                tags=trace['tags'],
                visibility=trace['visibility'],
                size=trace['size'],
                preview_line=encode_lonlat(trace['coords'].tolist(), 0),  # type: ignore
            )
            for trace in traces
        ],
        diaries_count=diaries_count_t.result(),
        diaries_comments_count=diaries_comments_count_t.result(),
        diaries=[
            ProfilePage.DiarySummary(
                id=diary['id'],
                created_at=int(diary['created_at'].timestamp()),
                title=diary['title'],
                num_comments=diary['num_comments'],  # type: ignore
            )
            for diary in diaries_t.result()
        ],
        groups_count=groups_count,
    )

    return await render_proto_page(
        profile_page_state,
        title_prefix=user['display_name'],
    )
