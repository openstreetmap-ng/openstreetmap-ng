from datetime import timedelta

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from config import HTTPS_ONLY, NAME, SECRET
from middlewares.auth_middleware import AuthMiddleware
from middlewares.request_middleware import RequestMiddleware
from middlewares.translation_middleware import LanguageMiddleware
from middlewares.version_middleware import VersionMiddleware
from responses.osm_response import OSMResponse

app = FastAPI(
    title=NAME,
    default_response_class=OSMResponse,
)
app.add_middleware(RequestMiddleware)
app.add_middleware(VersionMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET,
    session_cookie='_osm_session',
    max_age=int(timedelta(days=365).total_seconds()),
    https_only=HTTPS_ONLY,
)
app.add_middleware(AuthMiddleware)
app.add_middleware(LanguageMiddleware)
