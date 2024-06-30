import cython
from shapely import get_coordinates
from starlette.responses import HTMLResponse

from app.config import API_URL, APP_URL, TEST_ENV
from app.lib.auth_context import auth_user
from app.lib.jinja_env import render
from app.lib.locale import map_i18next_files
from app.lib.translation import translation_languages
from app.limits import MAP_QUERY_AREA_MAX_SIZE, NOTE_QUERY_AREA_MAX_SIZE
from app.middlewares.request_context_middleware import get_request
from app.models.editor import DEFAULT_EDITOR
from app.utils import JSON_ENCODE

_config_base = {
    'apiUrl': API_URL,
    'mapQueryAreaMaxSize': MAP_QUERY_AREA_MAX_SIZE,
    'noteQueryAreaMaxSize': NOTE_QUERY_AREA_MAX_SIZE,
}


@cython.cfunc
def _get_default_data() -> dict:
    user = auth_user()
    languages = translation_languages()

    # config: don't include sensitive data, it's exposed to iD/Rapid
    config: dict = _config_base.copy()

    if user is not None:
        config['activityTracking'] = user.activity_tracking
        config['crashReporting'] = user.crash_reporting

        user_home_point = user.home_point
        if user_home_point is not None:
            config['homePoint'] = get_coordinates(user_home_point)[0].tolist()

    return {
        'request': get_request(),
        'TEST_ENV': TEST_ENV,
        'APP_URL': APP_URL,
        'DEFAULT_EDITOR': DEFAULT_EDITOR,
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
