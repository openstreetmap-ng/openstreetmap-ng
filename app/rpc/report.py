from typing import override

from connectrpc.request import RequestContext

from app.lib.auth_context import require_web_user
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.models.proto.report_connect import (
    Service as ReportServiceConnect,
)
from app.models.proto.report_connect import ServiceASGIApplication
from app.models.proto.report_pb2 import (
    CreateRequest,
    CreateResponse,
)
from app.services.report_service import ReportService


class _Service(ReportServiceConnect):
    @override
    async def create(self, request: CreateRequest, ctx: RequestContext):
        require_web_user()

        await ReportService.create_report(
            type=CreateRequest.Type.Name(request.type),
            type_id=request.type_id,  # type: ignore
            action=CreateRequest.Action.Name(request.action),
            action_id=request.action_id if request.HasField('action_id') else None,  # type: ignore
            body=request.body,
            category=CreateRequest.Category.Name(request.category),
        )

        return CreateResponse(
            feedback=StandardFeedback.success_feedback(
                None,
                t(
                    'report.your_report_has_been_received_and_will_be_reviewed_by_our_team'
                ),
            ),
        )


service = _Service()
asgi_app_cls = ServiceASGIApplication
