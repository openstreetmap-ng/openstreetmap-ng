from asyncio import TaskGroup
from typing import assert_never, override

from connectrpc.request import RequestContext
from psycopg.sql import SQL
from starlette.exceptions import HTTPException
from starlette.status import HTTP_404_NOT_FOUND

from app.config import REPORT_COMMENTS_PAGE_SIZE, REPORT_LIST_PAGE_SIZE
from app.lib.auth_context import auth_user, require_web_user
from app.lib.date_utils import datetime_unix
from app.lib.standard_feedback import StandardFeedback
from app.lib.standard_pagination import sp_paginate_table
from app.lib.translation import t
from app.models.db.report import Report
from app.models.db.report_comment import (
    ReportComment,
    report_comments_resolve_rich_text,
)
from app.models.db.user import user_is_admin, user_is_moderator, user_proto
from app.models.proto.admin_users_pb2 import Role as ProtoRole
from app.models.proto.report_connect import (
    Service,
    ServiceASGIApplication,
)
from app.models.proto.report_pb2 import (
    Action as ProtoAction,
)
from app.models.proto.report_pb2 import (
    AddCommentRequest,
    AddCommentResponse,
    CommentBody,
    CreateRequest,
    CreateResponse,
    Header,
    ListCommentsRequest,
    ListCommentsResponse,
    ListRequest,
    ListResponse,
    ObjectInfo,
    UpdateCommentVisibilityRequest,
    UpdateCommentVisibilityResponse,
)
from app.models.proto.report_pb2 import (
    Category as ProtoCategory,
)
from app.models.proto.report_pb2 import (
    Status as ProtoStatus,
)
from app.models.proto.report_pb2 import (
    Type as ProtoType,
)
from app.models.proto.shared_pb2 import StandardPaginationRequest
from app.models.types import ReportCommentId, ReportId
from app.queries.report_comment_query import ReportCommentQuery
from app.queries.report_query import ReportQuery, where_open
from app.queries.user_query import UserQuery
from app.services.report_comment_service import ReportCommentService
from app.services.report_service import ReportService


class _Service(Service):
    @override
    async def create(self, request: CreateRequest, ctx: RequestContext):
        require_web_user()

        await ReportService.create_report(
            type=ProtoType.Name(request.type),
            type_id=request.type_id,  # type: ignore
            action=ProtoAction.Name(request.action),
            action_id=request.action_id if request.HasField('action_id') else None,  # type: ignore
            body=request.body,
            category=ProtoCategory.Name(request.category),
        )

        return CreateResponse(
            feedback=StandardFeedback.success_feedback(
                None,
                t(
                    'report.your_report_has_been_received_and_will_be_reviewed_by_our_team'
                ),
            ),
        )

    @override
    async def list(self, request: ListRequest, ctx: RequestContext):
        require_web_user('role_moderator')

        match request.status:
            case ProtoStatus.open:
                open: bool | None = True
            case ProtoStatus.closed:
                open = False
            case _:
                open = None

        reports, state = await sp_paginate_table(
            Report,
            request.state,
            table='report',
            where=where_open(open),
            page_size=REPORT_LIST_PAGE_SIZE,
            cursor_column='updated_at',
            cursor_kind='datetime',
            order_dir='desc',
        )

        async with TaskGroup() as tg:
            user_reports = [r for r in reports if r['type'] == 'user']
            if user_reports:
                tg.create_task(
                    UserQuery.resolve_users(
                        user_reports,
                        user_id_key='type_id',
                        user_key='reported_user',
                    )
                )
            tg.create_task(ReportCommentQuery.resolve_num_comments(reports))
            comments = await ReportCommentQuery.resolve_comments(
                reports, per_report_limit=1
            )
            tg.create_task(UserQuery.resolve_users(comments))
            tg.create_task(report_comments_resolve_rich_text(comments))
            tg.create_task(ReportCommentQuery.resolve_objects(comments))

        response = ListResponse()
        response.state.CopyFrom(state)
        for report in reports:
            entry = response.entries.add()
            _populate_header(entry.header, report)
            entry.num_comments = report.get('num_comments', 0)
            preview = (report.get('comments') or [None])[-1]
            if preview is not None:
                _populate_comment_body(entry.last_comment, preview)
        return response

    @override
    async def list_comments(self, request: ListCommentsRequest, ctx: RequestContext):
        require_web_user('role_moderator')
        report_id = ReportId(request.report_id)
        await _resolve_report(report_id)
        return await _build_list_comments_response(request.state, report_id)

    @override
    async def add_comment(self, request: AddCommentRequest, ctx: RequestContext):
        require_web_user('role_moderator')
        report_id = ReportId(request.report_id)
        match request.event:
            case ProtoAction.close:
                await ReportService.set_state(report_id, request.body, close=True)
            case ProtoAction.reopen:
                await ReportService.set_state(report_id, request.body, close=False)
            case ProtoAction.comment:
                await ReportService.add_comment(report_id, request.body)
            case _:
                assert_never(request.event)
        header, comments = await _build_show_state(report_id)
        return AddCommentResponse(header=header, comments=comments)

    @override
    async def update_comment_visibility(
        self, request: UpdateCommentVisibilityRequest, ctx: RequestContext
    ):
        require_web_user('role_administrator')
        await ReportCommentService.update_visibility(
            ReportCommentId(request.comment_id),
            ProtoRole.Name(request.visible_to),
        )
        return UpdateCommentVisibilityResponse()


async def _resolve_report(report_id: ReportId):
    report = await ReportQuery.find_by_id(report_id)
    if report is None:
        raise HTTPException(HTTP_404_NOT_FOUND, 'Report not found')
    return report


async def build_report_header(report_id: ReportId):
    """Build the proto Header for a report. Shared between the show controller
    (SSR bootstrap) and mutation responses on the rpc service.
    """
    report = await _resolve_report(report_id)
    if report['type'] == 'user':
        await UserQuery.resolve_users(
            [report],
            user_id_key='type_id',
            user_key='reported_user',
        )
    header = Header()
    _populate_header(header, report)
    return header


async def _build_list_comments_response(
    state_request: StandardPaginationRequest, report_id: ReportId
):
    comments, state = await sp_paginate_table(
        ReportComment,
        state_request,
        table='report_comment',
        where=t'report_id = {report_id}',
        page_size=REPORT_COMMENTS_PAGE_SIZE,
        cursor_column='created_at',
        cursor_kind='datetime',
        order_dir='desc',
        display_dir='asc',
    )

    is_moderator = user_is_moderator(auth_user())
    is_admin = user_is_admin(auth_user())
    for comment in comments:
        comment['has_access'] = (
            comment['visible_to'] == 'moderator' and is_moderator
        ) or (comment['visible_to'] == 'administrator' and is_admin)

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(comments))
        tg.create_task(report_comments_resolve_rich_text(comments))
        tg.create_task(ReportCommentQuery.resolve_objects(comments))

    response = ListCommentsResponse()
    response.state.CopyFrom(state)
    for comment in comments:
        entry = response.entries.add()
        entry.id = comment['id']
        entry.created_at = datetime_unix(comment['created_at'])
        entry.visible_to = ProtoRole.Value(comment['visible_to'])
        _populate_comment_body(entry.body, comment)
    return response


async def _build_show_state(report_id: ReportId):
    """Refresh the show page state after a mutation: header + first comments page,
    fetched in parallel.
    """
    async with TaskGroup() as tg:
        header_task = tg.create_task(build_report_header(report_id))
        comments_task = tg.create_task(
            _build_list_comments_response(StandardPaginationRequest(), report_id)
        )
    return header_task.result(), comments_task.result()


def _populate_header(header: Header, report: Report):
    header.id = report['id']
    header.updated_at = datetime_unix(report['updated_at'])
    if report['closed_at'] is not None:
        header.closed_at = datetime_unix(report['closed_at'])
    if report['type'] == 'anonymous_note':
        header.anonymous_note_id = report['type_id']
        return
    # TODO: synthesize a placeholder `deleted_<UID>` user when resolve_users
    # comes back empty (hard-deleted account) so this assertion holds and the
    # client never has to special-case missing-user state.
    reported_user = report['reported_user']  # type: ignore[typeddict-item]
    header.reported_user.CopyFrom(user_proto(reported_user))


def _populate_comment_body(body: CommentBody, comment: ReportComment):
    body.action = ProtoAction.Value(comment['action'])
    if (category := comment['category']) is not None:
        body.category = ProtoCategory.Value(category)
    if (action_id := comment['action_id']) is not None:
        body.action_id = action_id
    # Setting body_rich (even to empty string) marks the body as accessible;
    # leaving it unset is the only state for "viewer lacks access".
    if comment.get('has_access'):
        body.body_rich = comment.get('body_rich') or ''
    if (user_msg := user_proto(comment.get('user'))) is not None:
        body.user.CopyFrom(user_msg)
    obj = comment.get('object')
    if obj is None:
        return
    info = ObjectInfo()
    match comment['action']:
        case 'user_diary':
            info.diary_title = obj['title']  # type: ignore
        case 'user_message':
            info.message_subject = obj['subject']  # type: ignore
        case 'user_oauth2_application':
            info.oauth2_app.name = obj['name']  # type: ignore
            info.oauth2_app.redirect_uris.extend(obj.get('redirect_uris') or [])
        case 'user_trace':
            info.trace_name = obj['name']  # type: ignore
        case _:
            return
    body.object.CopyFrom(info)


service = _Service()
asgi_app_cls = ServiceASGIApplication
