import contextvars
import traceback
from asyncio import DefaultEventLoopPolicy, Task
from functools import partial
from pathlib import Path


# https://github.com/pytest-dev/pytest-asyncio/issues/127#issuecomment-2062158881
def task_factory(loop, coro, context=None):
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


class CustomEventLoopPolicy(DefaultEventLoopPolicy):
    __slots__ = ('_context',)

    def __init__(self) -> None:
        super().__init__()
        self._context = contextvars.copy_context()

    def new_event_loop(self):
        loop = self._loop_factory()  # type: ignore[attr-defined]
        loop.set_task_factory(partial(task_factory, context=self._context))
        return loop
