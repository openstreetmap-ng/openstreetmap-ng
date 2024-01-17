from datetime import timedelta

from fastapi import FastAPI
from middlewares.auth_middleware import AuthMiddleware
from middlewares.request_middleware import RequestMiddleware
from middlewares.translation_middleware import LanguageMiddleware
from middlewares.version_middleware import VersionMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from app.config import HTTPS_ONLY, NAME, SECRET
from app.responses.osm_response import OSMResponse

# TODO: trust proxy
# https://stackoverflow.com/questions/73450371/url-for-is-using-http-instead-of-https-in-fastapi
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

app.mount('/static', StaticFiles(directory='app/static'), name='static')
