from asyncio import Event, Queue, Task, get_running_loop

from starlette.types import ASGIApp, Message


class LifespanManager:
    __slots__ = ('_app', '_exc', '_message_queue', '_shutdown_finished', '_startup_finished', '_task')

    def __init__(self, app: ASGIApp) -> None:
        self._app = app
        self._task: Task | None = None
        self._message_queue: Queue[Message] = Queue()
        self._startup_finished = Event()
        self._shutdown_finished = Event()
        self._exc: BaseException | None = None

    async def _receive(self) -> Message:
        return await self._message_queue.get()

    async def _send(self, message: Message) -> None:
        if message['type'] == 'lifespan.startup.complete':
            self._startup_finished.set()
        elif message['type'] == 'lifespan.shutdown.complete':
            self._shutdown_finished.set()

    async def _run(self):
        try:
            await self._app({'type': 'lifespan'}, self._receive, self._send)
        except BaseException as e:
            self._exc = e
            raise
        finally:
            self._startup_finished.set()
            self._shutdown_finished.set()

    async def __aenter__(self):
        if self._task is not None:
            raise RuntimeError('Lifespan is already running')

        self._task = get_running_loop().create_task(self._run())
        self._message_queue.put_nowait({'type': 'lifespan.startup'})
        await self._startup_finished.wait()
        if self._exc is not None:
            raise self._exc

    async def __aexit__(self, exc_type, exc_value, traceback):
        if self._exc is not None:  # skip cleanup if startup failed
            return
        if self._task is None:
            raise RuntimeError('Lifespan is not running')

        self._message_queue.put_nowait({'type': 'lifespan.shutdown'})
        await self._shutdown_finished.wait()
        if self._exc is not None:
            raise self._exc  # pyright: ignore[reportGeneralTypeIssues]
        self._task.cancel()
        self._task = None
