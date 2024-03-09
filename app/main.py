import gc
import importlib
import logging
import mimetypes
import pathlib
import sys
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from starlette.routing import Router

import app.lib.cython_detect  # DO NOT REMOVE  # noqa: F401
from app.config import (
    ID_VERSION,
    LOCALE_DIR,
    NAME,
    RAPID_VERSION,
    TEST_ENV,
)
from app.middlewares.auth_middleware import AuthMiddleware
from app.middlewares.cache_control_middleware import CacheControlMiddleware
from app.middlewares.compress_middleware import CompressMiddleware
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
from app.responses.osm_response import setup_api_router_response
from app.responses.precompressed_static_files import PrecompressedStaticFiles

# register additional mimetypes
mimetypes.init()
mimetypes.add_type('application/javascript', '.cjs')

# harden against parsing really big numbers
sys.set_int_max_str_digits(sys.int_info.str_digits_check_threshold)

# reduce gc frequency and enable debug logging
gc.set_threshold(10_000, 10, 10)

if logging.root.level <= logging.DEBUG:
    gc.set_debug(gc.DEBUG_STATS)

# log when in test environment
if TEST_ENV:
    logging.info('🦺 Running in test environment')


@asynccontextmanager
async def lifespan(_):
    # TODO: gc threshold + debug
    # freeze uncollected gc objects for improved performance
    gc.collect()
    gc.freeze()
    yield


main = FastAPI(title=NAME, lifespan=lifespan)

main.add_middleware(UnsupportedBrowserMiddleware)  # depends on: session, translation
main.add_middleware(CompressMiddleware)
main.add_middleware(CacheControlMiddleware)  # depends on: request
main.add_middleware(RateLimitMiddleware)  # depends on: request
main.add_middleware(RequestContextMiddleware)
main.add_middleware(FormatStyleMiddleware)  # TODO: check raise before this middleware
main.add_middleware(TranslationMiddleware)  # depends on: auth
main.add_middleware(AuthMiddleware)
main.add_middleware(RequestBodyMiddleware)
main.add_middleware(RequestUrlMiddleware)
main.add_middleware(ExceptionsMiddleware)
main.add_middleware(VersionMiddleware)
main.add_middleware(RuntimeMiddleware)

if TEST_ENV:
    main.add_middleware(ProfilerMiddleware)

# TODO: /static default cache control
main.mount('/static', PrecompressedStaticFiles('app/static'), name='static')
main.mount('/static-locale', PrecompressedStaticFiles(LOCALE_DIR / 'i18next'), name='static-locale')
main.mount(
    '/static-bootstrap-icons',
    PrecompressedStaticFiles('node_modules/bootstrap-icons/font/fonts'),
    name='static-bootstrap-icons',
)
main.mount(
    f'/static-id/{ID_VERSION}',
    PrecompressedStaticFiles('node_modules/iD/dist'),
    name='static-id',
)
main.mount(
    f'/static-rapid/{RAPID_VERSION}',
    PrecompressedStaticFiles('node_modules/@rapideditor/rapid/dist'),
    name='static-rapid',
)


def _make_router(path: str, prefix: str) -> APIRouter:
    """
    Create a router from all modules in the given path.
    """
    router = APIRouter(prefix=prefix)
    router_counter = 0
    routes_counter = 0

    for p in pathlib.Path(path).glob('*.py'):
        module_name = p.with_suffix('').as_posix().replace('/', '.')
        module = importlib.import_module(module_name)
        router_attr: Router | None = getattr(module, 'router', None)

        if router_attr is not None:
            setup_api_router_response(router_attr)
            router.include_router(router_attr)
            router_counter += 1
            routes_counter += len(router_attr.routes)
        else:
            logging.warning('Router not found in %s', module_name)

    logging.info('Loaded (%d routers, %d routes) from %s as %r', router_counter, routes_counter, path, prefix)
    return router


main.include_router(_make_router('app/controllers', ''))
main.include_router(_make_router('app/controllers/api', '/api'))
main.include_router(_make_router('app/controllers/api/v06', '/api/0.6'))
main.include_router(_make_router('app/controllers/api/web', '/api/web'))
main.include_router(_make_router('app/controllers/api/web/partial', '/api/web/partial'))
