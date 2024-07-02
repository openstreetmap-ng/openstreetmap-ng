from collections.abc import Sequence

from anyio import TASK_STATUS_IGNORED, create_task_group
from anyio.abc import TaskStatus
from feedgen.feed import FeedGenerator

from app.models.db.changeset import Changeset


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
