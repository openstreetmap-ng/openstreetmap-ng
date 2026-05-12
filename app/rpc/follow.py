from typing import override

from connectrpc.request import RequestContext

from app.lib.auth_context import require_web_user
from app.lib.date_utils import datetime_unix
from app.models.db.user import user_proto
from app.models.proto.follow_connect import (
    Service,
    ServiceASGIApplication,
)
from app.models.proto.follow_pb2 import (
    ListRequest,
    ListResponse,
    Tab,
    UpdateRequest,
    UpdateResponse,
)
from app.models.types import UserId
from app.queries.user_follow_query import UserFollowQuery
from app.services.user_follow_service import UserFollowService


class _Service(Service):
    @override
    async def update(self, request: UpdateRequest, ctx: RequestContext):
        require_web_user()

        target_user_id = UserId(request.target_user_id)
        if request.is_following:
            await UserFollowService.follow(target_user_id)
        else:
            await UserFollowService.unfollow(target_user_id)

        return UpdateResponse()

    @override
    async def list(self, request: ListRequest, ctx: RequestContext):
        user = require_web_user()

        followers = request.tab == Tab.followers
        rows, state = await UserFollowQuery.paginate(
            user['id'], request.state, followers=followers
        )

        response = ListResponse()
        response.state.CopyFrom(state)
        for row in rows:
            entry = response.entries.add()
            entry.user.CopyFrom(user_proto(row))  # type: ignore
            entry.since = datetime_unix(row['created_at'])
            entry.is_following = row['is_following']  # type: ignore
        return response


service = _Service()
asgi_app_cls = ServiceASGIApplication
