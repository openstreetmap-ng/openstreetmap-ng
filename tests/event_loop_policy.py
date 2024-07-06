import contextvars
import traceback
from asyncio import Task
from pathlib import Path

import uvloop


# inspired by https://github.com/pytest-dev/pytest-asyncio/issues/127#issuecomment-2062158881
def get_task_factory(default_context: contextvars.Context):
    def task_factory(loop, coro, context=None):
        if context is None:
            context = default_context
        stack = traceback.extract_stack()
        for frame in stack[-2::-1]:
            package_name = Path(frame.filename).parts[-2]
            if package_name != 'asyncio':
                if package_name == 'pytest_asyncio':
                    # This function was called from pytest_asyncio, use shared context
                    break
                else:
                    # This function was called from somewhere else, create context copy
                    context = None
                break
        return Task(coro, loop=loop, context=context)

    return task_factory


class CustomEventLoopPolicy(uvloop.EventLoopPolicy):
    __slots__ = ('_context',)

    def __init__(self) -> None:
        super().__init__()
        self._context = contextvars.copy_context()

    def new_event_loop(self):
        loop = self._loop_factory()
        loop.set_task_factory(get_task_factory(self._context))
        return loop
