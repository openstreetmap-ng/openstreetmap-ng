from typing import override

from connectrpc.request import RequestContext

from app.lib.auth_context import require_web_user
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.models.proto.report_connect import (
    ReportService as ReportServiceConnect,
)
from app.models.proto.report_connect import (
    ReportServiceASGIApplication,
)
from app.models.proto.report_pb2 import (
    CreateReportRequest,
    CreateReportResponse,
)
from app.services.report_service import ReportService


class _Service(ReportServiceConnect):
    @override
    async def create_report(self, request: CreateReportRequest, ctx: RequestContext):
        require_web_user()

        await ReportService.create_report(
            type=CreateReportRequest.Type.Name(request.type),
            type_id=request.type_id,  # type: ignore
            action=CreateReportRequest.Action.Name(request.action),
            action_id=request.action_id,  # type: ignore
            body=request.body,
            category=CreateReportRequest.Category.Name(request.category),
        )

        return CreateReportResponse(
            feedback=StandardFeedback.success_feedback(
                None,
                t(
                    'report.your_report_has_been_received_and_will_be_reviewed_by_our_team'
                ),
            ),
        )


service = _Service()
asgi_app_cls = ReportServiceASGIApplication
