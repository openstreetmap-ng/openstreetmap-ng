import cython
from shapely import get_coordinates
from starlette.responses import HTMLResponse

from app.config import API_URL, APP_URL, ID_URL, ID_VERSION, RAPID_URL, RAPID_VERSION
from app.lib.auth_context import auth_user
from app.lib.locale import map_i18next_files
from app.lib.translation import render, translation_languages
from app.limits import MAP_QUERY_AREA_MAX_SIZE, NOTE_QUERY_AREA_MAX_SIZE
from app.middlewares.request_context_middleware import get_request
from app.utils import JSON_ENCODE


@cython.cfunc
def _get_default_data() -> dict:
    user = auth_user()
    languages = translation_languages()

    if (user is not None) and (user_home_point := user.home_point) is not None:
        home_point = get_coordinates(user_home_point)[0].tolist()
    else:
        home_point = None

    config = {
        'apiUrl': API_URL,
        'idUrl': ID_URL,
        'idVersion': ID_VERSION,
        'rapidUrl': RAPID_URL,
        'rapidVersion': RAPID_VERSION,
        'languages': languages,
        'homePoint': home_point,
        'mapQueryAreaMaxSize': MAP_QUERY_AREA_MAX_SIZE,
        'noteQueryAreaMaxSize': NOTE_QUERY_AREA_MAX_SIZE,
    }

    return {
        'request': get_request(),
        'APP_URL': APP_URL,
        'lang': languages[0],
        'user': user,
        'config': JSON_ENCODE(config).decode(),
        'i18next_files': map_i18next_files(languages),
    }


def render_response(template_name: str, template_data: dict | None = None) -> HTMLResponse:
    """
    Render the given Jinja2 template with translation.
    """

    data = _get_default_data()

    if template_data is not None:
        data.update(template_data)

    return HTMLResponse(render(template_name, **data))
