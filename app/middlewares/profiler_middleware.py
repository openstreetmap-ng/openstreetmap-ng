import cython
from fastapi import Request
from pyinstrument import Profiler
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse


class ProfilerMiddleware(BaseHTTPMiddleware):
    """
    Add ability to profile requests via `?profile=1` query param.
    """

    # https://pyinstrument.readthedocs.io/en/latest/guide.html#profile-a-web-request-in-fastapi
    async def dispatch(self, request: Request, call_next):
        profile: cython.char = 'profile' in request.query_params

        if not profile:
            return await call_next(request)

        profiler = Profiler()
        profiler.start()
        await call_next(request)
        profiler.stop()

        return HTMLResponse(profiler.output_html())
