from shapely import get_coordinates
from starlette.responses import HTMLResponse

from app.config import API_URL
from app.lib.auth_context import auth_user
from app.lib.jinja_env import render
from app.lib.locale import map_i18next_files
from app.lib.translation import translation_locales
from app.limits import MAP_QUERY_AREA_MAX_SIZE, NOTE_QUERY_AREA_MAX_SIZE
from app.middlewares.request_context_middleware import get_request
from app.models.editor import DEFAULT_EDITOR
from app.utils import JSON_ENCODE

_config_dict_base = {
    'apiUrl': API_URL,
    'mapQueryAreaMaxSize': MAP_QUERY_AREA_MAX_SIZE,
    'noteQueryAreaMaxSize': NOTE_QUERY_AREA_MAX_SIZE,
}

_config = JSON_ENCODE(_config_dict_base).decode()


def render_response(template_name: str, template_data: dict | None = None) -> HTMLResponse:
    """
    Render the given Jinja2 template with translation, returning an HTMLResponse.
    """
    user = auth_user()
    locales = translation_locales()

    if user is not None:
        # don't include sensitive data, it's exposed to JavaScript
        config_dict: dict = _config_dict_base.copy()
        config_dict['activityTracking'] = user.activity_tracking
        config_dict['crashReporting'] = user.crash_reporting

        user_home_point = user.home_point
        if user_home_point is not None:
            config_dict['homePoint'] = get_coordinates(user_home_point)[0].tolist()

        config = JSON_ENCODE(config_dict).decode()
    else:
        config = _config

    data = {
        'request': get_request(),
        'DEFAULT_EDITOR': DEFAULT_EDITOR,
        'config': config,
        'i18next_files': map_i18next_files(locales),
    }
    if template_data is not None:
        data.update(template_data)
    return HTMLResponse(render(template_name, data))
