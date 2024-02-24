import gc
import importlib
import logging
import mimetypes
import pathlib
import sys
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

import app.lib.cython_detect  # DO NOT REMOVE  # noqa: F401
from app.config import (
    COOKIE_SESSION_TTL,
    HTTPS_ONLY,
    ID_ASSETS_DIR,
    ID_VERSION,
    LOCALE_DIR,
    NAME,
    RAPID_ASSETS_DIR,
    RAPID_VERSION,
    SECRET,
    TEST_ENV,
)
from app.middlewares.auth_middleware import AuthMiddleware
from app.middlewares.cache_control_middleware import CacheControlMiddleware
from app.middlewares.exceptions_middleware import ExceptionsMiddleware
from app.middlewares.format_style_middleware import FormatStyleMiddleware
from app.middlewares.profiler_middleware import ProfilerMiddleware
from app.middlewares.rate_limit_middleware import RateLimitMiddleware
from app.middlewares.request_body_middleware import RequestBodyMiddleware
from app.middlewares.request_context_middleware import RequestContextMiddleware
from app.middlewares.request_url_middleware import RequestUrlMiddleware
from app.middlewares.runtime_middleware import RuntimeMiddleware
from app.middlewares.translation_middleware import TranslationMiddleware
from app.middlewares.unsupported_browser_middleware import UnsupportedBrowserMiddleware
from app.middlewares.version_middleware import VersionMiddleware
from app.responses.osm_response import OSMResponse

# register additional mimetypes
mimetypes.init()
mimetypes.add_type('application/javascript', '.cjs')

# warn against unsafe cookies
if not HTTPS_ONLY and not TEST_ENV:
    logging.warning('HTTPS_ONLY cookies are disabled (unsafe)')

# log when in test environment
if TEST_ENV:
    logging.info('🦺 Running in test environment')


@asynccontextmanager
async def lifespan(_):
    # TODO: gc threshold + debug
    # freeze uncollected gc objects for improved performance
    gc.collect()
    gc.freeze()

    # harden against parsing really big numbers
    sys.set_int_max_str_digits(sys.int_info.str_digits_check_threshold)

    yield


main = FastAPI(
    title=NAME,
    default_response_class=OSMResponse,
    lifespan=lifespan,
)

main.add_middleware(UnsupportedBrowserMiddleware)  # depends on: session, translation
main.add_middleware(CacheControlMiddleware)  # depends on: request
main.add_middleware(RateLimitMiddleware)  # depends on: request
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
main.add_middleware(ExceptionsMiddleware)

if TEST_ENV:
    main.add_middleware(RuntimeMiddleware)
    main.add_middleware(ProfilerMiddleware)

# TODO: /static default cache control
main.mount('/static', StaticFiles(directory='app/static'), name='static')
main.mount('/static-locale', StaticFiles(directory=LOCALE_DIR / 'i18next'), name='static-locale')
main.mount('/node_modules', StaticFiles(directory='node_modules'), name='node_modules')
main.mount(f'/static-id/{ID_VERSION}', StaticFiles(directory=ID_ASSETS_DIR), name='static-id')
main.mount(f'/static-rapid/{RAPID_VERSION}', StaticFiles(directory=RAPID_ASSETS_DIR), name='static-rapid')


def _make_router(path: str, prefix: str) -> APIRouter:
    """
    Create a router from all modules in the given path.
    """
    router = APIRouter(prefix=prefix)
    counter = 0

    for p in pathlib.Path(path).glob('*.py'):
        module_name = p.with_suffix('').as_posix().replace('/', '.')
        module = importlib.import_module(module_name)
        router_attr = getattr(module, 'router', None)

        if router_attr is not None:
            router.include_router(router_attr)
            counter += 1
        else:
            logging.warning('Missing router in %s', module_name)

    logging.info('Loaded %d routers from %s as %r', counter, path, prefix)
    return router


main.include_router(_make_router('app/controllers', ''))
main.include_router(_make_router('app/controllers/api', '/api'))
main.include_router(_make_router('app/controllers/api/v06', '/api/0.6'))
main.include_router(_make_router('app/controllers/api/web', '/api/web'))
main.include_router(_make_router('app/controllers/api/web/partial', '/api/web/partial'))
