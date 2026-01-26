from typing import override

from connectrpc.request import RequestContext

from app.controllers.web_changeset import build_changeset_data
from app.models.proto.changeset_connect import (
    ChangesetService,
    ChangesetServiceASGIApplication,
)
from app.models.proto.changeset_pb2 import GetChangesetRequest, GetChangesetResponse
from app.models.types import ChangesetId


class _Service(ChangesetService):
    @override
    async def get_changeset(
        self, request: GetChangesetRequest, ctx: RequestContext
    ) -> GetChangesetResponse:
        return GetChangesetResponse(
            changeset=await build_changeset_data(ChangesetId(request.id))
        )


service = _Service()
asgi_app_cls = ChangesetServiceASGIApplication
