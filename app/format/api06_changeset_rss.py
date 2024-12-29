from collections.abc import Sequence

import cython
from feedgen.entry import FeedEntry
from feedgen.feed import FeedGenerator

from app.config import APP_URL
from app.lib.date_utils import format_rfc2822_date
from app.lib.jinja_env import render
from app.lib.translation import t
from app.models.db.changeset import Changeset


class ChangesetRSS06Mixin:
    @staticmethod
    async def encode_changesets(fg: FeedGenerator, changesets: Sequence[Changeset]) -> None:
        """
        Encode changesets into a feed.
        """
        fg.load_extension('geo')
        for changeset in changesets:
            _encode_changeset(fg, changeset)


@cython.cfunc
def _encode_changeset(fg: FeedGenerator, changeset: Changeset):
    fe: FeedEntry = fg.add_entry(order='append')
    fe.id(f'{APP_URL}/changeset/{changeset.id}')
    fe.published(changeset.created_at)
    fe.updated(changeset.updated_at)
    fe.link(rel='alternate', type='text/html', href=f'{APP_URL}/changeset/{changeset.id}')
    fe.link(rel='alternate', type='application/osm+xml', href=f'{APP_URL}/api/0.6/changeset/{changeset.id}')
    fe.link(
        rel='alternate', type='application/osmChange+xml', href=f'{APP_URL}/api/0.6/changeset/{changeset.id}/download'
    )

    tags = changeset.tags
    comment = tags.get('comment')
    if comment is not None:
        fe.title(f'{t("browse.changeset.feed.title_comment", id=changeset.id, comment=comment)}')
    else:
        fe.title(f'{t("browse.changeset.feed.title", id=changeset.id)}')

    if changeset.user_id is not None:
        user = changeset.user
        if user is None:
            raise AssertionError('Changeset user must be set')
        user_display_name = user.display_name
        user_permalink = f'{APP_URL}/user-id/{user.id}'
        fe.author(name=user_display_name, uri=user_permalink)
    else:
        user_display_name = None
        user_permalink = None

    if changeset.union_bounds is not None:
        minx, miny, maxx, maxy = changeset.union_bounds.bounds
        fe.geo.box(f'{miny} {minx} {maxy} {maxx}')

    fe.content(
        render(
            'api06/history_feed_entry.jinja2',
            {
                'created': format_rfc2822_date(changeset.created_at),
                'closed': format_rfc2822_date(changeset.closed_at) if (changeset.closed_at is not None) else None,
                'user_display_name': user_display_name,
                'user_permalink': user_permalink,
                'tags': tags,
            },
        ),
        type='xhtml',
    )
