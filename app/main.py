import gc
import importlib
import logging
import mimetypes
import os
import pathlib
import sys
import traceback
from contextlib import asynccontextmanager
from time import tzset

import fastapi.dependencies.utils
import fastapi.routing
from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.asyncexitstack import AsyncExitStackMiddleware
from sentry_sdk import capture_exception
from starlette import concurrency as starlette_concurrency
from starlette import status
from starlette.applications import Starlette
from starlette.convertors import register_url_convertor
from starlette.middleware import Middleware
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.middleware.exceptions import ExceptionMiddleware
from starlette.types import ASGIApp
from starlette_compress import CompressMiddleware

import app.lib.cython_detect  # DO NOT REMOVE
import app.lib.sentry
from app.config import (
    COMPRESS_HTTP_BROTLI_QUALITY,
    COMPRESS_HTTP_GZIP_LEVEL,
    COMPRESS_HTTP_MIN_SIZE,
    COMPRESS_HTTP_ZSTD_LEVEL,
    ENV,
    NAME,
)
from app.db import psycopg_pool_open
from app.lib.starlette_convertor import ElementTypeConvertor
from app.lib.user_name_blacklist import user_name_blacklist_routes
from app.middlewares.api_cors_middleware import APICorsMiddleware
from app.middlewares.auth_middleware import AuthMiddleware
from app.middlewares.cache_control_middleware import CacheControlMiddleware
from app.middlewares.default_headers_middleware import DefaultHeadersMiddleware
from app.middlewares.exceptions_middleware import ExceptionsMiddleware
from app.middlewares.format_style_middleware import FormatStyleMiddleware
from app.middlewares.limit_url_size_middleware import LimitUrlSizeMiddleware
from app.middlewares.localhost_redirect_middleware import LocalhostRedirectMiddleware
from app.middlewares.parallel_tasks_middleware import ParallelTasksMiddleware
from app.middlewares.profiler_middleware import ProfilerMiddleware
from app.middlewares.rate_limit_middleware import RateLimitMiddleware
from app.middlewares.request_body_middleware import RequestBodyMiddleware
from app.middlewares.request_context_middleware import RequestContextMiddleware
from app.middlewares.runtime_middleware import RuntimeMiddleware
from app.middlewares.subdomain_middleware import SubdomainMiddleware
from app.middlewares.test_site_middleware import TestSiteMiddleware
from app.middlewares.translation_middleware import TranslationMiddleware
from app.middlewares.unsupported_browser_middleware import UnsupportedBrowserMiddleware
from app.responses.osm_response import setup_api_router_response
from app.responses.precompressed_static_files import PrecompressedStaticFiles
from app.rpc.app import app as rpc_app
from app.services.admin_task_service import AdminTaskService
from app.services.audit_service import AuditService
from app.services.changeset_service import ChangesetService
from app.services.element_spatial_service import ElementSpatialService
from app.services.email_service import EmailService
from app.services.image_proxy_service import ImageProxyService
from app.services.system_app_service import SystemAppService
from app.services.test_service import TestService


# HACK: Execute sync functions directly without threadpool
async def _async_wrapper(func, *args, **kwargs):
    return func(*args, **kwargs)


starlette_concurrency.run_in_threadpool = _async_wrapper
fastapi.routing.run_in_threadpool = _async_wrapper
fastapi.dependencies.utils.run_in_threadpool = _async_wrapper

# set the timezone to UTC
# note that "export TZ=UTC" from shell.nix is unreliable for some users
os.environ['TZ'] = 'UTC'
tzset()

# register additional mimetypes
mimetypes.init()
mimetypes.add_type('application/javascript', '.cjs')
mimetypes.add_type('application/gpx+xml', '.gpx')

# harden against parsing huge numbers
sys.set_int_max_str_digits(sys.int_info.str_digits_check_threshold)

# reduce gc frequency and enable debug logging
gc.set_threshold(10_000, 10, 10)

# log when in test environment
if ENV != 'prod':
    logging.info('🦺 Running in %s environment', ENV)


@asynccontextmanager
async def lifespan(_):
    async with psycopg_pool_open(), AuditService.context():
        if ENV != 'prod':
            await TestService.on_startup()

        await SystemAppService.on_startup()

        async with (
            AdminTaskService.context(),
            ImageProxyService.context(),
            EmailService.context(),
            ChangesetService.context(),
            ElementSpatialService.context(),
        ):
            # freeze uncollected gc objects for improved performance
            gc.collect()
            gc.freeze()
            yield


register_url_convertor('element_type', ElementTypeConvertor())

app = FastAPI(
    debug=ENV != 'prod',
    title=NAME,
    lifespan=lifespan,
    openapi_url='/api/openapi.json',
    docs_url='/api/docs',
    redoc_url='/api/redoc',
)

app.add_middleware(ParallelTasksMiddleware)

if ENV == 'test':
    app.add_middleware(TestSiteMiddleware)

app.add_middleware(UnsupportedBrowserMiddleware)  # depends on: session, translation
app.add_middleware(
    CompressMiddleware,
    minimum_size=COMPRESS_HTTP_MIN_SIZE,
    zstd_level=COMPRESS_HTTP_ZSTD_LEVEL,
    brotli_quality=COMPRESS_HTTP_BROTLI_QUALITY,
    gzip_level=COMPRESS_HTTP_GZIP_LEVEL,
    # Workaround for ConnectRPC compression issues
    # https://github.com/connectrpc/connect-python/issues/96
    remove_accept_encoding=True,
)
app.add_middleware(CacheControlMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(FormatStyleMiddleware)
app.add_middleware(TranslationMiddleware)  # depends on: auth
app.add_middleware(AuthMiddleware)
app.add_middleware(RequestBodyMiddleware)
app.add_middleware(SubdomainMiddleware)
app.add_middleware(LimitUrlSizeMiddleware)
app.add_middleware(ExceptionsMiddleware)

if ENV == 'dev':
    app.add_middleware(LocalhostRedirectMiddleware)

if ENV != 'prod':
    app.add_middleware(ProfilerMiddleware)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(APICorsMiddleware)
app.add_middleware(DefaultHeadersMiddleware)

if ENV != 'prod':
    app.add_middleware(RuntimeMiddleware)

app.mount('/rpc', rpc_app, name='rpc')

# TODO: /static default cache control
app.mount(
    '/static/',
    PrecompressedStaticFiles('app/static'),
    name='static',
)
app.mount(
    '/static-locale/',
    PrecompressedStaticFiles('config/locale/i18next'),
    name='static-locale',
)
app.mount(
    '/static-node_modules/',
    PrecompressedStaticFiles('node_modules'),
    name='static-node_modules',
)


def _make_router(path: pathlib.Path, prefix: str) -> APIRouter:
    """Create a router from all modules in the given path."""
    router = APIRouter(prefix=prefix)
    router_counter: int = 0
    routes_counter: int = 0
    for p in sorted(path.glob('*.py')):
        module_name = p.as_posix().replace('/', '.')[:-3]
        module = importlib.import_module(module_name)
        router_attr: APIRouter | None = getattr(module, 'router', None)
        if not isinstance(router_attr, APIRouter):
            logging.warning('APIRouter not found in %s', module_name)
            continue
        setup_api_router_response(router_attr)
        router.include_router(router_attr)
        router_counter += 1
        routes_counter += len(router_attr.routes)
    logging.info(
        'Loaded %d routers, %d routes from %s as %r',
        router_counter,
        routes_counter,
        path,
        prefix,
    )
    return router


app.include_router(_make_router(pathlib.Path('app/controllers'), ''))
user_name_blacklist_routes(app)


def _build_middleware_stack(self: Starlette) -> ASGIApp:
    """Build an alternate middleware stack that runs ExceptionMiddleware before user middleware."""
    debug = self.debug
    error_handler = None
    exception_handlers = {}

    for key, value in self.exception_handlers.items():
        if key in (500, Exception):
            error_handler = value
        else:
            exception_handlers[key] = value

    middleware = [
        Middleware(ServerErrorMiddleware, handler=error_handler, debug=debug),
        Middleware(ExceptionMiddleware, handlers=exception_handlers, debug=debug),
        *self.user_middleware,
        Middleware(AsyncExitStackMiddleware),
    ]

    app = self.router
    for cls, args, kwargs in reversed(middleware):
        app = cls(app, *args, **kwargs)
    return app


app.build_middleware_stack = _build_middleware_stack.__get__(app, Starlette)


@app.exception_handler(ExceptionGroup)
async def exception_group_handler(request: Request, exc: ExceptionGroup):
    """Unpack supported exception groups."""
    for e in exc.exceptions:
        if isinstance(e, HTTPException):
            return await http_exception_handler(request, e)

    capture_exception(exc)
    traceback.print_exception(exc.__class__, exc, exc.__traceback__)
    return Response('Internal Server Error', status.HTTP_500_INTERNAL_SERVER_ERROR)


__all__ = ('app',)
