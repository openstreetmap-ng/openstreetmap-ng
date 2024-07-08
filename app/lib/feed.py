from typing import Annotated

from fastapi import Query
from feedgen.feed import FeedGenerator
from starlette import status
from starlette.responses import HTMLResponse

from app.config import APP_URL
from app.format import FormatRSS06
from app.lib.date_utils import utcnow
from app.lib.translation import primary_translation_language, t
from app.limits import CHANGESET_QUERY_DEFAULT_LIMIT, CHANGESET_QUERY_MAX_LIMIT
from app.queries.changeset_query import ChangesetQuery
from app.queries.user_query import UserQuery


async def get_history_feed(
    user_display_name: str | None = None,
    limit: Annotated[int, Query(gt=0, le=CHANGESET_QUERY_MAX_LIMIT)] = CHANGESET_QUERY_DEFAULT_LIMIT,
):
    if user_display_name:
        user = await UserQuery.find_one_by_display_name(display_name=user_display_name)
        if not user:
            return HTMLResponse(status_code=status.HTTP_404_NOT_FOUND, media_type='application/atom+xml')
        else:
            user_id = user.id
    else:
        user_id = None
    changesets = await ChangesetQuery.find_many_by_query(
        user_id=user_id,
        limit=limit,
    )
    if len(changesets) == 0:
        return HTMLResponse(status_code=status.HTTP_404_NOT_FOUND, media_type='application/atom+xml')
    fg = FeedGenerator()
    fg.link(rel='self', type='text/html', href=f'{APP_URL}/history/feed')
    fg.link(
        rel='alternate',
        type='application/atom+xml',
        href=f'{APP_URL}/history/feed',
    )
    fg.title(t('changesets.index.title'))
    fg.logo(f'{APP_URL}/static/img/favicon/logo.svg')
    fg.icon(f'{APP_URL}/static/img/favicon/64.webp')
    fg.language(primary_translation_language())
    fg.id(f'{APP_URL}/history/feed')
    fg.updated(utcnow())
    fg.rights('CC BY-SA 2.0')
    await FormatRSS06.encode_changesets(fg, changesets)
    return fg.atom_str(pretty=True)
