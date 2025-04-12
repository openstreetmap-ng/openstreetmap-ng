import cython
from feedgen.entry import FeedEntry
from feedgen.feed import FeedGenerator

from app.config import APP_URL
from app.lib.date_utils import format_rfc2822_date
from app.lib.render_jinja import render_jinja
from app.lib.translation import t
from app.models.db.changeset import Changeset


class ChangesetRSS06Mixin:
    @staticmethod
    def encode_changesets(fg: FeedGenerator, changesets: list[Changeset]) -> None:
        """Encode changesets into a feed."""
        fg.load_extension('geo')
        for changeset in changesets:
            _encode_changeset(fg, changeset)


@cython.cfunc
def _encode_changeset(fg: FeedGenerator, changeset: Changeset):
    changeset_id = changeset['id']
    created_at = changeset['created_at']
    updated_at = changeset['updated_at']
    closed_at = changeset['closed_at']

    fe: FeedEntry = fg.add_entry(order='append')
    fe.id(f'{APP_URL}/changeset/{changeset_id}')
    fe.published(created_at)
    fe.updated(updated_at)
    fe.link(rel='alternate', type='text/html', href=f'{APP_URL}/changeset/{changeset_id}')
    fe.link(rel='alternate', type='application/osm+xml', href=f'{APP_URL}/api/0.6/changeset/{changeset_id}')
    fe.link(
        rel='alternate',
        type='application/osmChange+xml',
        href=f'{APP_URL}/api/0.6/changeset/{changeset_id}/download',
    )

    tags = changeset['tags']
    comment = tags.get('comment')
    if comment is not None:
        fe.title(f'{t("browse.changeset.feed.title_comment", id=changeset_id, comment=comment)}')
    else:
        fe.title(f'{t("browse.changeset.feed.title", id=changeset_id)}')

    user_id = changeset['user_id']
    if user_id is not None:
        user_display_name = changeset['user']['display_name']  # pyright: ignore [reportTypedDictNotRequiredAccess]
        user_permalink = f'{APP_URL}/user-id/{user_id}'
        fe.author(name=user_display_name, uri=user_permalink)
    else:
        user_display_name = None
        user_permalink = None

    union_bounds = changeset['union_bounds']
    if union_bounds is not None:
        minx, miny, maxx, maxy = union_bounds.bounds
        fe.geo.box(f'{miny} {minx} {maxy} {maxx}')

    fe.content(
        render_jinja(
            'api06/history-feed-entry',
            {
                'created': format_rfc2822_date(created_at),
                'closed': format_rfc2822_date(closed_at) if (closed_at is not None) else None,
                'user_display_name': user_display_name,
                'user_permalink': user_permalink,
                'tags': tags,
            },
        ),
        type='xhtml',
    )
