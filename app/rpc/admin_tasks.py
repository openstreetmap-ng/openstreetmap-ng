from typing import override

from connectrpc.request import RequestContext

from app.lib.auth_context import require_web_user
from app.lib.standard_feedback import StandardFeedback
from app.models.proto.admin_tasks_connect import (
    Service,
    ServiceASGIApplication,
)
from app.models.proto.admin_tasks_pb2 import (
    ListRequest,
    ListResponse,
    StartRequest,
    StartResponse,
)
from app.services.admin_task_service import AdminTaskService, TaskId


class _Service(Service):
    @override
    async def list(self, request: ListRequest, ctx: RequestContext):
        require_web_user('role_administrator')
        tasks = await AdminTaskService.list_tasks()
        return ListResponse(
            tasks=[
                ListResponse.Task(
                    id=task['id'],
                    arguments=[
                        ListResponse.Task.Argument(
                            name=name,
                            type=arg['type'],
                            required=arg['required'],
                            default=arg['default'],
                            numeric=arg['numeric'],
                        )
                        for name, arg in task['arguments'].items()
                    ],
                    running=task['running'],
                )
                for task in tasks
            ]
        )

    @override
    async def start(self, request: StartRequest, ctx: RequestContext):
        require_web_user('role_administrator')

        try:
            AdminTaskService.start_task(TaskId(request.task_id), request.arguments)
        except ValueError as e:
            StandardFeedback.raise_error('task_id', str(e), exc=e)

        return StartResponse()


service = _Service()
asgi_app_cls = ServiceASGIApplication
