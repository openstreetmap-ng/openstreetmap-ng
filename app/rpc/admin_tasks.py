from typing import override

from connectrpc.request import RequestContext

from app.lib.auth.context import require_web_user
from app.lib.standard.feedback import StandardFeedback
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
        response = ListResponse()
        for task in tasks:
            response_task = response.tasks.add()
            response_task.id = task['id']
            for name, arg in task['arguments'].items():
                argument = response_task.arguments.add()
                argument.name = name
                argument.type = arg['type']
                argument.required = arg['required']
                argument.default = arg['default']
                argument.numeric = arg['numeric']
            response_task.running = task['running']
        return response

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
