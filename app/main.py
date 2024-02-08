import gc
import mimetypes
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.exceptions import ExceptionMiddleware
from starlette.middleware.sessions import SessionMiddleware

import app.controllers.index
import app.lib.cython_detect  # DO NOT REMOVE
from app.config import COOKIE_SESSION_TTL, HTTPS_ONLY, LOCALE_DIR, NAME, SECRET, TEST_ENV
from app.middlewares.auth_middleware import AuthMiddleware
from app.middlewares.format_style_middleware import FormatStyleMiddleware
from app.middlewares.profiler_middleware import ProfilerMiddleware
from app.middlewares.request_body_middleware import RequestBodyMiddleware
from app.middlewares.request_context_middleware import RequestContextMiddleware
from app.middlewares.request_url_middleware import RequestUrlMiddleware
from app.middlewares.runtime_middleware import RuntimeMiddleware
from app.middlewares.translation_middleware import TranslationMiddleware
from app.middlewares.version_middleware import VersionMiddleware
from app.responses.caching_static_files import CachingStaticFiles
from app.responses.osm_response import OSMResponse

# register additional mimetypes
mimetypes.init()
mimetypes.add_type('application/javascript', '.cjs')


@asynccontextmanager
async def lifespan(_):
    # freeze all gc objects before starting for improved performance
    gc.collect()
    gc.freeze()

    yield


main = FastAPI(
    title=NAME,
    default_response_class=OSMResponse,
    lifespan=lifespan,
)

main.add_middleware(RequestContextMiddleware)
main.add_middleware(VersionMiddleware)
main.add_middleware(FormatStyleMiddleware)  # TODO: check raise before this middleware
main.add_middleware(TranslationMiddleware)  # depends on: auth
main.add_middleware(AuthMiddleware)  # depends on: session
main.add_middleware(
    SessionMiddleware,
    secret_key=SECRET,
    session_cookie='session',
    max_age=COOKIE_SESSION_TTL,
    https_only=HTTPS_ONLY,
)
main.add_middleware(RequestBodyMiddleware)
main.add_middleware(RequestUrlMiddleware)
main.add_middleware(ExceptionMiddleware)

if TEST_ENV:
    main.add_middleware(RuntimeMiddleware)
    main.add_middleware(ProfilerMiddleware)

main.mount('/static', CachingStaticFiles('app/static'), name='static')
main.mount('/static-locale', CachingStaticFiles(LOCALE_DIR / 'i18next'), name='static-locale')

if TEST_ENV:
    main.mount('/node_modules', CachingStaticFiles('node_modules'), name='node_modules')

main.include_router(app.controllers.index.router)
