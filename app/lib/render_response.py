from typing import Any

from shapely import get_coordinates
from starlette.responses import HTMLResponse

from app.config import API_URL
from app.lib.auth_context import auth_user
from app.lib.jinja_env import render
from app.lib.locale import map_i18next_files
from app.lib.translation import translation_locales
from app.limits import MAP_QUERY_AREA_MAX_SIZE, NOTE_QUERY_AREA_MAX_SIZE
from app.middlewares.parallel_tasks_middleware import ParallelTasksMiddleware
from app.middlewares.request_context_middleware import get_request
from app.models.db.user import Editor
from app.utils import json_encodes

_default_editor = Editor.get_default().value
_config_dict_base: dict[str, Any] = {
    'apiUrl': API_URL,
    'mapQueryAreaMaxSize': MAP_QUERY_AREA_MAX_SIZE,
    'noteQueryAreaMaxSize': NOTE_QUERY_AREA_MAX_SIZE,
}
_config = json_encodes(_config_dict_base)


async def render_response(template_name: str, template_data: dict[str, Any] | None = None) -> HTMLResponse:
    """
    Render the given Jinja2 template with translation, returning an HTMLResponse.
    """
    data = {
        'request': get_request(),
        'i18next_files': map_i18next_files(translation_locales()),
        'default_editor': _default_editor,
        'config': _config,
    }

    user = auth_user()
    if user is not None:
        # don't include sensitive data, it's exposed to JavaScript
        config_dict = _config_dict_base.copy()
        config_dict['activityTracking'] = user.activity_tracking
        config_dict['crashReporting'] = user.crash_reporting

        user_home_point = user.home_point
        if user_home_point is not None:
            config_dict['homePoint'] = get_coordinates(user_home_point)[0].tolist()

        data['config'] = json_encodes(config_dict)

        messages_count_unread = await ParallelTasksMiddleware.messages_count_unread()
        if messages_count_unread is not None:
            data['messages_count_unread'] = messages_count_unread

    if template_data is not None:
        data.update(template_data)
    return HTMLResponse(render(template_name, data))
