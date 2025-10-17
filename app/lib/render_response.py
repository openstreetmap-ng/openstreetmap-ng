from base64 import urlsafe_b64encode
from typing import Any

from shapely import get_coordinates
from starlette.responses import HTMLResponse

from app.config import (
    API_URL,
    ENV,
    MAP_QUERY_AREA_MAX_SIZE,
    NOTE_QUERY_AREA_MAX_SIZE,
    VERSION,
)
from app.lib.auth_context import auth_user
from app.lib.locale import INSTALLED_LOCALES_NAMES_MAP, map_i18next_files
from app.lib.render_jinja import render_jinja
from app.lib.sentry import SENTRY_DSN, SENTRY_TRACES_SAMPLE_RATE
from app.lib.translation import translation_locales
from app.middlewares.parallel_tasks_middleware import ParallelTasksMiddleware
from app.middlewares.request_context_middleware import get_request
from app.models.proto.shared_pb2 import WebConfig

_CONFIG_BASE = WebConfig(
    sentry_config=(
        WebConfig.SentryConfig(
            dsn=SENTRY_DSN,
            traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
        )
        if SENTRY_DSN
        else None
    ),
    version=VERSION,
    env=ENV,
    api_url=API_URL,
    map_query_area_max_size=MAP_QUERY_AREA_MAX_SIZE,
    note_query_area_max_size=NOTE_QUERY_AREA_MAX_SIZE,
    locales=[
        WebConfig.Locale(
            code=code,
            native_name=locale_name.native,
            english_name=(
                locale_name.english
                if locale_name.english != locale_name.native
                else None
            ),
            flag=locale_name.flag,
        )
        for code, locale_name in INSTALLED_LOCALES_NAMES_MAP.items()
    ],
)
_CONFIG_DEFAULT = urlsafe_b64encode(_CONFIG_BASE.SerializeToString()).decode()


async def render_response(
    template_name: str,
    template_data: dict[str, Any] | None = None,
    *,
    status: int = 200,
) -> HTMLResponse:
    """Render the given Jinja2 template with translation, returning an HTMLResponse."""
    data = {
        'request': get_request(),
        'I18NEXT_FILES': map_i18next_files(translation_locales()),
        'WEB_CONFIG': _CONFIG_DEFAULT,
    }

    user = auth_user()
    if user is not None:
        user_config = WebConfig.UserConfig(
            id=user['id'],
            activity_tracking=user['activity_tracking'],
            crash_reporting=user['crash_reporting'],
        )

        user_home_point = user['home_point']
        if user_home_point is not None:
            x, y = get_coordinates(user_home_point)[0].tolist()
            user_config.home_point = WebConfig.UserConfig.HomePoint(lon=x, lat=y)

        web_config = WebConfig(user_config=user_config)
        web_config.MergeFrom(_CONFIG_BASE)
        data['WEB_CONFIG'] = urlsafe_b64encode(web_config.SerializeToString()).decode()

        messages_count_unread = await ParallelTasksMiddleware.messages_count_unread()
        if messages_count_unread is not None:
            data['MESSAGES_COUNT_UNREAD'] = messages_count_unread

        reports_count_attention = (
            await ParallelTasksMiddleware.reports_count_attention()
        )
        if reports_count_attention is not None:
            data['REPORTS_COUNT_MODERATOR'] = reports_count_attention.moderator
            data['REPORTS_COUNT_ADMINISTRATOR'] = reports_count_attention.administrator

    if template_data is not None:
        data.update(template_data)

    return HTMLResponse(render_jinja(template_name, data), status_code=status)
