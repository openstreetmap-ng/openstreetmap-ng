from collections.abc import Iterable
from datetime import datetime
from typing import TYPE_CHECKING, NewType, NotRequired, TypedDict

from psycopg import AsyncConnection
from shapely import Polygon

from app.lib.user_role_limits import UserRoleLimits
from app.models.db.user import User, UserId

if TYPE_CHECKING:
    from app.models.db.changeset_bounds import ChangesetBounds
    from app.models.db.changeset_comment import ChangesetComment

ChangesetId = NewType('ChangesetId', int)


class ChangesetInit(TypedDict):
    user_id: UserId | None
    tags: dict[str, str]


class Changeset(ChangesetInit):
    id: ChangesetId
    # TODO: normalize unicode, check unicode, check length
    # TODO: test updated at optimistic
    created_at: datetime
    updated_at: datetime
    closed_at: datetime
    size: int
    union_bounds: Polygon | None

    # runtime
    user: NotRequired[User]
    bounds: NotRequired[list['ChangesetBounds']]
    num_comments: NotRequired[int]
    comments: NotRequired[list['ChangesetComment'] | None]


def changeset_set_size(changeset: Changeset, new_size: int) -> bool:
    """Try to change the changeset size. Returns True if successful."""
    if changeset['size'] >= new_size:
        raise ValueError('New size must be greater than the current size')

    if changeset['user_id']:
        user = changeset.get('user')
        assert user is not None, 'Changeset user must be set'
        max_size = UserRoleLimits.get_changeset_max_size(user.roles)
    else:
        max_size = UserRoleLimits.get_changeset_max_size(())

    if new_size > max_size:
        return False
    changeset['size'] = new_size
    return True


async def changesets_auto_close_on_size(conn: AsyncConnection, changesets: Iterable[Changeset]) -> int:
    """Close changesets that have reached the maximum size. Returns the number of updated changesets."""
    mapping: dict[int, Changeset] = {}

    for changeset in changesets:
        if changeset['closed_at'] is not None:
            continue

        if changeset['user_id']:
            user = changeset.get('user')
            assert user is not None, 'Changeset user must be set'
            max_size = UserRoleLimits.get_changeset_max_size(user.roles)
        else:
            max_size = UserRoleLimits.get_changeset_max_size(())

        if changeset['size'] >= max_size:
            mapping[changeset['id']] = changeset

    if not mapping:
        return 0

    async with await conn.execute(
        """
        SELECT closed_at
        FROM (
            UPDATE changeset
            SET closed_at = STATEMENT_TIMESTAMP()
            WHERE id = ANY(%s)
            RETURNING closed_at
        ) LIMIT 1
        """,
        (list(mapping),),
    ) as r:
        row = await r.fetchone()
        assert row is not None
        closed_at: datetime = row[0]

    for changeset in mapping.values():
        changeset['closed_at'] = closed_at

    return len(mapping)
