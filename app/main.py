import gc
import importlib
import logging
import mimetypes
import os
import pathlib
import sys
import time
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from fastapi.exception_handlers import http_exception_handler
from starlette import status
from starlette.convertors import register_url_convertor
from starlette_compress import CompressMiddleware

import app.lib.cython_detect  # DO NOT REMOVE  # noqa: F401
from app.config import (
    GC_LOG,
    ID_VERSION,
    NAME,
    RAPID_VERSION,
    TEST_ENV,
)
from app.lib.starlette_convertor import ElementTypeConvertor
from app.limits import (
    COMPRESS_HTTP_BROTLI_QUALITY,
    COMPRESS_HTTP_GZIP_LEVEL,
    COMPRESS_HTTP_MIN_SIZE,
    COMPRESS_HTTP_ZSTD_LEVEL,
)
from app.middlewares.auth_middleware import AuthMiddleware
from app.middlewares.cache_control_middleware import CacheControlMiddleware
from app.middlewares.exceptions_middleware import ExceptionsMiddleware
from app.middlewares.format_style_middleware import FormatStyleMiddleware
from app.middlewares.limit_url_size_middleware import LimitUrlSizeMiddleware
from app.middlewares.parallel_tasks_middleware import ParallelTasksMiddleware
from app.middlewares.profiler_middleware import ProfilerMiddleware
from app.middlewares.rate_limit_middleware import RateLimitMiddleware
from app.middlewares.request_body_middleware import RequestBodyMiddleware
from app.middlewares.request_context_middleware import RequestContextMiddleware
from app.middlewares.runtime_middleware import RuntimeMiddleware
from app.middlewares.translation_middleware import TranslationMiddleware
from app.middlewares.unsupported_browser_middleware import UnsupportedBrowserMiddleware
from app.middlewares.version_middleware import VersionMiddleware
from app.responses.osm_response import setup_api_router_response
from app.responses.precompressed_static_files import PrecompressedStaticFiles
from app.services.email_service import EmailService
from app.services.system_app_service import SystemAppService
from app.services.test_service import TestService

# set the timezone to UTC
# note that "export TZ=UTC" from shell.nix is unreliable for some users
os.environ['TZ'] = 'UTC'
time.tzset()

# register additional mimetypes
mimetypes.init()
mimetypes.add_type('application/javascript', '.cjs')
mimetypes.add_type('application/gpx+xml', '.gpx')

# harden against parsing really big numbers
sys.set_int_max_str_digits(sys.int_info.str_digits_check_threshold)

# reduce gc frequency and enable debug logging
gc.set_threshold(10_000, 10, 10)

if GC_LOG and logging.root.level <= logging.DEBUG:
    gc.set_debug(gc.DEBUG_STATS)

# log when in test environment
if TEST_ENV:
    logging.info('🦺 Running in test environment')


@asynccontextmanager
async def lifespan(_):
    # freeze uncollected gc objects for improved performance
    gc.collect()
    gc.freeze()

    if TEST_ENV:
        await TestService.on_startup()

    await SystemAppService.on_startup()

    async with EmailService.context():
        yield


register_url_convertor('element_type', ElementTypeConvertor())

main = FastAPI(title=NAME, lifespan=lifespan)

main.add_middleware(ParallelTasksMiddleware)
main.add_middleware(UnsupportedBrowserMiddleware)  # depends on: session, translation
main.add_middleware(
    CompressMiddleware,
    minimum_size=COMPRESS_HTTP_MIN_SIZE,
    zstd_level=COMPRESS_HTTP_ZSTD_LEVEL,
    brotli_quality=COMPRESS_HTTP_BROTLI_QUALITY,
    gzip_level=COMPRESS_HTTP_GZIP_LEVEL,
)
main.add_middleware(CacheControlMiddleware)
main.add_middleware(RateLimitMiddleware)
main.add_middleware(FormatStyleMiddleware)  # TODO: check raise before this middleware
main.add_middleware(TranslationMiddleware)  # depends on: auth
main.add_middleware(AuthMiddleware)
main.add_middleware(RequestBodyMiddleware)
main.add_middleware(LimitUrlSizeMiddleware)
main.add_middleware(ExceptionsMiddleware)

if TEST_ENV:
    main.add_middleware(ProfilerMiddleware)

main.add_middleware(RequestContextMiddleware)

if TEST_ENV:
    main.add_middleware(VersionMiddleware)
    main.add_middleware(RuntimeMiddleware)


# TODO: /static default cache control
main.mount('/static', PrecompressedStaticFiles('app/static'), name='static')
main.mount('/static-locale', PrecompressedStaticFiles('config/locale/i18next'), name='static-locale')
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
        router_attr: APIRouter | None = getattr(module, 'router', None)

        if isinstance(router_attr, APIRouter):
            setup_api_router_response(router_attr)
            router.include_router(router_attr)
            router_counter += 1
            routes_counter += len(router_attr.routes)
        else:
            logging.warning('APIRouter not found in %s', module_name)

    logging.info('Loaded (%d routers, %d routes) from %s as %r', router_counter, routes_counter, path, prefix)
    return router


main.include_router(_make_router('app/controllers', ''))


@main.exception_handler(ExceptionGroup)
async def exception_group_handler(request: Request, exc: ExceptionGroup):
    """
    Unpack supported exception groups.
    """
    http_exception = next((e for e in exc.exceptions if isinstance(e, HTTPException)), None)
    if http_exception is not None:
        return await http_exception_handler(request, http_exception)
    return Response('Internal Server Error', status.HTTP_500_INTERNAL_SERVER_ERROR)
