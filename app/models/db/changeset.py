from datetime import datetime
from typing import TYPE_CHECKING, Literal, NotRequired, TypedDict

from shapely import MultiPolygon, Polygon

from app.lib.auth_context import auth_user
from app.lib.user_role_limits import UserRoleLimits
from app.models.db.user import UserDisplay
from app.models.types import ChangesetId, UserId

if TYPE_CHECKING:
    from app.models.db.changeset_comment import ChangesetComment


class ChangesetInit(TypedDict):
    user_id: UserId | None
    tags: dict[str, str]


class Changeset(ChangesetInit):
    id: ChangesetId
    # TODO: normalize unicode, check unicode, check length
    # TODO: test updated at optimistic
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    size: int
    num_create: int
    num_modify: int
    num_delete: int
    union_bounds: Polygon | None

    # runtime
    user: NotRequired[UserDisplay]
    bounds: NotRequired[MultiPolygon]
    num_comments: NotRequired[int]
    comments: NotRequired[list['ChangesetComment']]
    size_limit_reached: NotRequired[Literal[True]]


def changeset_increase_size(changeset: Changeset, *, num_create: int, num_modify: int, num_delete: int) -> bool:
    """Try to increase the changeset size. Returns True if successful."""
    assert num_create >= 0, 'num_create must be non-negative'
    assert num_modify >= 0, 'num_modify must be non-negative'
    assert num_delete >= 0, 'num_delete must be non-negative'

    user = auth_user(required=True)
    user_id = user['id']
    max_size = UserRoleLimits.get_changeset_max_size(user['roles'])

    changeset_user_id = changeset['user_id']
    assert changeset_user_id is not None, 'Anonymous changesets are no longer supported'
    assert changeset_user_id == user_id, f'Changeset {changeset["id"]} can only be edited by the owner != {user_id}'

    new_size = changeset['size'] + num_create + num_modify + num_delete
    if new_size > max_size:
        return False

    if new_size == max_size:
        changeset['size_limit_reached'] = True  # type: ignore

    changeset['size'] = new_size
    changeset['num_create'] += num_create
    changeset['num_modify'] += num_modify
    changeset['num_delete'] += num_delete
    return True
