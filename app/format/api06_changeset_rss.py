from collections.abc import Sequence

from anyio import TASK_STATUS_IGNORED, create_task_group
from anyio.abc import TaskStatus
from feedgen.feed import FeedGenerator

from app.config import APP_URL
from app.lib.translation import t
from app.models.db.changeset import Changeset
from app.queries.user_query import UserQuery


class ChangesetRSS06Mixin:
    @staticmethod
    async def encode_changesets(fg: FeedGenerator, changesets: Sequence[Changeset]) -> dict:
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
    user = await UserQuery.find_one_by_id(user_id=changeset.user_id)
    fe.author(
        name=user.display_name,
        uri=f'{APP_URL}/user/{user.display_name}',
    )
    fe.link(rel='alternate', type='text/html', href=f'{APP_URL}/changeset/{changeset.id}')
    fe.link(rel='alternate', type='application/osm+xml', href=f'{APP_URL}/api/0.6/changeset/{changeset.id}')
    fe.link(
        rel='alternate', type='application/osmChange+xml', href=f'{APP_URL}/api/0.6/changeset/{changeset.id}/download'
    )
