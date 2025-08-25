from datetime import datetime
from typing import Any, override

import cython
from jinja2 import Environment, FileSystemLoader
from jinja2_htmlmin import minify_loader

from app.config import APP_URL, ENV, REPORT_COMMENT_BODY_MAX_LENGTH, VERSION
from app.lib.auth_context import auth_user
from app.lib.date_utils import format_rfc2822_date, utcnow
from app.lib.image import Image
from app.lib.locale import INSTALLED_LOCALES_NAMES_MAP
from app.lib.translation import nt, primary_translation_locale, t
from app.lib.vite import vite_render_asset
from app.models.db.connected_account import CONFIGURED_AUTH_PROVIDERS
from app.models.db.oauth2_application import oauth2_app_avatar_url, oauth2_app_is_system
from app.models.db.user import (
    DEFAULT_EDITOR,
    user_avatar_url,
    user_is_admin,
    user_is_deleted,
    user_is_moderator,
)
from speedup.element_type import split_typed_element_id

if cython.compiled:
    from cython.cimports.libc.math import ceil
else:
    from math import ceil


class _FileSystemLoader(FileSystemLoader):
    @override
    def get_source(self, environment, template):
        return super().get_source(environment, template + '.html.jinja')


_J2 = Environment(
    loader=minify_loader(
        _FileSystemLoader('app/views'),
        remove_comments=True,
        remove_empty_space=True,
        remove_all_empty_space=True,
        reduce_boolean_attributes=True,
    ),
    autoescape=True,
    cache_size=1024,
    auto_reload=ENV == 'dev',
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=False,
)


def render_jinja(
    template_name: str, template_data: dict[str, Any] | None = None, /
) -> str:
    """Render the given Jinja2 template with translation."""
    data = {
        'ENV': ENV,
        'VERSION': VERSION,
        'APP_URL': APP_URL,
        'user': auth_user(),
        'lang': primary_translation_locale(),
    }

    if template_data is not None:
        data.update(template_data)

    return _J2.get_template(template_name).render(data)


def timeago(date: datetime | None, *, html: bool = False) -> str:
    """
    Get a human-readable time difference from the given date.
    Optionally, return the result as an HTML <time> element.

    >>> timeago(datetime(2021, 12, 31, 15, 30, 45))
    'an hour ago'
    >>> timeago(datetime(2021, 12, 31, 15, 30, 45), html=True)
    '<time datetime="2021-12-31T15:30:45Z" title="31 December 2021 at 15:30">an hour ago</time>'
    >>> timeago(None)
    'never'
    """
    if date is None:
        return t('time.never')

    total_seconds: cython.double = (utcnow() - date).total_seconds()

    if total_seconds < 1:
        # less than 1 second ago
        ago = nt('datetime.distance_in_words_ago.less_than_x_seconds', 1)
    elif total_seconds < 30:
        # X seconds ago
        ago = nt('datetime.distance_in_words_ago.x_seconds', ceil(total_seconds))
    elif total_seconds < 45:
        # half a minute ago
        ago = t('datetime.distance_in_words_ago.half_a_minute')
    elif total_seconds < 60:
        # less than a minute ago
        ago = nt('datetime.distance_in_words_ago.less_than_x_minutes', 1)
    elif total_seconds < 3600:
        # X minutes ago
        ago = nt(
            'datetime.distance_in_words_ago.x_minutes',
            int(total_seconds / 60),
        )
    elif total_seconds < (3600 * 24):
        # about X hours ago
        ago = nt(
            'datetime.distance_in_words_ago.about_x_hours',
            int(total_seconds / 3600),
        )
    elif total_seconds < (3600 * 24 * 30):
        # X days ago
        ago = nt(
            'datetime.distance_in_words_ago.x_days',
            int(total_seconds / (3600 * 24)),
        )
    elif total_seconds < (3600 * 24 * 330):
        # X months ago
        ago = nt(
            'datetime.distance_in_words_ago.x_months',
            int(total_seconds / (3600 * 24 * 30)),
        )
    elif total_seconds % (3600 * 24 * 365) < (3600 * 24 * 330):
        # X years ago
        ago = nt(
            'datetime.distance_in_words_ago.x_years',
            int(total_seconds / (3600 * 24 * 365)),
        )
    else:
        # almost X years ago
        ago = nt(
            'datetime.distance_in_words_ago.almost_x_years',
            int(ceil(total_seconds / (3600 * 24 * 365))),  # noqa: RUF046
        )

    if html:
        return f'<time datetime="{date.isoformat()}" title="{date.strftime(t("time.formats.friendly"))}">{ago}</time>'

    return ago


# TODO: ideally we should fix translation
def stripspecial(value: str) -> str:
    """Strip special characters from the given string."""
    return value.strip('!?:;., ')


# configure template globals
_J2.globals.update(
    CONFIGURED_AUTH_PROVIDERS=CONFIGURED_AUTH_PROVIDERS,
    DEFAULT_EDITOR=DEFAULT_EDITOR,
    INSTALLED_LOCALES_NAMES_MAP=INSTALLED_LOCALES_NAMES_MAP,
    REPORT_COMMENT_BODY_MAX_LENGTH=REPORT_COMMENT_BODY_MAX_LENGTH,
    format_rfc2822_date=format_rfc2822_date,
    get_avatar_url=Image.get_avatar_url,
    nt=nt,
    oauth2_app_avatar_url=oauth2_app_avatar_url,
    oauth2_app_is_system=oauth2_app_is_system,
    round=round,
    split_typed_element_id=split_typed_element_id,
    str=str,
    t=t,
    timeago=timeago,
    user_avatar_url=user_avatar_url,
    user_is_admin=user_is_admin,
    user_is_deleted=user_is_deleted,
    user_is_moderator=user_is_moderator,
    vite_render_asset=vite_render_asset,
    zip=zip,
)

# configure template filters
_J2.filters.update(
    stripspecial=stripspecial,
)
