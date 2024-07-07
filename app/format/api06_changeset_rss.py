from collections.abc import Sequence

from anyio import TASK_STATUS_IGNORED, create_task_group
from anyio.abc import TaskStatus
from feedgen.feed import FeedGenerator

from app.config import APP_URL
from app.lib.jinja_env import render
from app.lib.translation import t
from app.models.db.changeset import Changeset
from app.queries.user_query import UserQuery

FE_DATETIME_FORMAT = '%a, %d %b %Y %H:%M:%S +0000'


class ChangesetRSS06Mixin:
    @staticmethod
    async def encode_changesets(fg: FeedGenerator, changesets: Sequence[Changeset]) -> None:
        """
        Encode changesets into a feed.
        """

        async with create_task_group() as tg:
            for changeset in changesets:
                await tg.start(_encode_changeset, fg, changeset)


async def _encode_changeset(
    fg: FeedGenerator,
    changeset: Changeset,
    task_status: TaskStatus = TASK_STATUS_IGNORED,
) -> None:
    # use task_status to preserve the order of the changesets
    task_status.started()

    fe = fg.add_entry(order='append')
    fe.title(f'{t("browse.changeset.feed.title",id=changeset.id)}')
    fe.id(f'{APP_URL}/changeset/{changeset.id}')
    fe.updated(changeset.updated_at)
    fe.published(changeset.created_at)

    if changeset.user_id:
        user = await UserQuery.find_one_by_id(user_id=changeset.user_id)
        author_name = user.display_name if user else ''
    else:
        author_name = ''
    author_uri = f'{APP_URL}/user/{author_name}'
    fe.author(
        name=author_name,
        uri=author_uri,
    )

    fe.link(rel='alternate', type='text/html', href=f'{APP_URL}/changeset/{changeset.id}')
    fe.link(rel='alternate', type='application/osm+xml', href=f'{APP_URL}/api/0.6/changeset/{changeset.id}')
    fe.link(
        rel='alternate', type='application/osmChange+xml', href=f'{APP_URL}/api/0.6/changeset/{changeset.id}/download'
    )

    if changeset.closed_at is not None:
        closed = changeset.closed_at.strftime(FE_DATETIME_FORMAT)
    else:
        closed = ''

    fe.content(
        render(
            'index/history_feed_entry_content.jinja2',
            created=changeset.created_at.strftime(FE_DATETIME_FORMAT),
            closed=closed,
            author_name=author_name,
            author_uri=author_uri,
            tags=changeset.tags,
        ),
        type='xhtml',
    )
