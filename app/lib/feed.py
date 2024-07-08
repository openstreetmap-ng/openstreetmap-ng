from fastapi import Response
from feedgen.feed import FeedGenerator
from sqlalchemy.orm import joinedload
from starlette import status

from app.config import APP_URL, ATTRIBUTION_URL
from app.format import FormatRSS06
from app.lib.date_utils import utcnow
from app.lib.options_context import options_context
from app.lib.translation import primary_translation_language, t
from app.models.db.changeset import Changeset
from app.models.db.user import User
from app.queries.changeset_query import ChangesetQuery
from app.queries.user_query import UserQuery


async def get_history_feed(
    *,
    user_display_name: str | None = None,
    limit: int,
):
    if user_display_name is not None:
        user = await UserQuery.find_one_by_display_name(display_name=user_display_name)
        if user is None:
            return Response(None, status.HTTP_404_NOT_FOUND, media_type='application/atom+xml')
        user_id = user.id
    else:
        user_id = None

    with options_context(joinedload(Changeset.user).load_only(User.display_name)):
        changesets = await ChangesetQuery.find_many_by_query(user_id=user_id, limit=limit)
    if not changesets:
        return Response(None, status.HTTP_404_NOT_FOUND, media_type='application/atom+xml')

    fg = FeedGenerator()
    fg.language(primary_translation_language())
    fg.id(f'{APP_URL}/history/feed')
    fg.updated(utcnow())
    fg.link(rel='self', type='text/html', href=f'{APP_URL}/history/feed')
    fg.link(
        rel='alternate',
        type='application/atom+xml',
        href=f'{APP_URL}/history/feed',
    )
    fg.title(t('changesets.index.title'))
    fg.icon(f'{APP_URL}/static/img/favicon/64.webp')
    fg.logo(f'{APP_URL}/static/img/favicon/256.webp')
    fg.rights(ATTRIBUTION_URL)
    await FormatRSS06.encode_changesets(fg, changesets)
    return fg.atom_str(pretty=True)
