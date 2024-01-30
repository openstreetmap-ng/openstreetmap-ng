import gc
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI
from middlewares.auth_middleware import AuthMiddleware
from middlewares.translation_middleware import TranslationMiddleware
from middlewares.version_middleware import VersionMiddleware
from starlette.middleware.exceptions import ExceptionMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

import app.lib.cython_detect  # DO NOT REMOVE
from app.config import HTTPS_ONLY, LOCALE_DIR, NAME, SECRET, TEST_ENV
from app.middlewares.format_style_middleware import FormatStyleMiddleware
from app.middlewares.profiler_middleware import ProfilerMiddleware
from app.middlewares.request_body_middleware import RequestBodyMiddleware
from app.middlewares.request_url_middleware import RequestUrlMiddleware
from app.middlewares.runtime_middleware import RuntimeMiddleware
from app.responses.osm_response import OSMResponse


@asynccontextmanager
async def lifespan():
    # freeze all gc objects before starting for improved performance
    gc.collect()
    gc.freeze()

    yield


app = FastAPI(
    title=NAME,
    default_response_class=OSMResponse,
    lifespan=lifespan,
)

app.add_middleware(VersionMiddleware)
app.add_middleware(FormatStyleMiddleware)  # TODO: check raise before this middleware
app.add_middleware(TranslationMiddleware)  # depends on: auth
app.add_middleware(AuthMiddleware)  # depends on: session
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET,
    session_cookie='_osm_session',
    max_age=int(timedelta(days=365).total_seconds()),
    https_only=HTTPS_ONLY,
)
app.add_middleware(RequestBodyMiddleware)
app.add_middleware(RequestUrlMiddleware)
app.add_middleware(ExceptionMiddleware)

if TEST_ENV:
    app.add_middleware(RuntimeMiddleware)
    app.add_middleware(ProfilerMiddleware)

app.mount('/static', StaticFiles(directory='app/static'), name='static')
app.mount('/static-locale', StaticFiles(directory=str(LOCALE_DIR / 'i18next')), name='static-locale')
