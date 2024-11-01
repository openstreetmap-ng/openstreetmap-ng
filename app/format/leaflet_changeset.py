from collections.abc import Iterable

import cython

from app.lib.jinja_env import timeago
from app.models.db.changeset import Changeset
from app.models.proto.shared_pb2 import RenderChangesetData, RenderChangesetsData, SharedBounds


class LeafletChangesetMixin:
    @staticmethod
    def encode_changesets(changesets: Iterable[Changeset]) -> RenderChangesetsData:
        """
        Format changesets into a minimal structure, suitable for map rendering.
        """
        return RenderChangesetsData(changesets=tuple(_encode_changeset(changeset) for changeset in changesets))


@cython.cfunc
def _encode_changeset(changeset: Changeset):
    num_comments = changeset.num_comments
    if num_comments is None:
        raise AssertionError('Changeset num comments must be set')
    if changeset.user_id is not None:
        changeset_user = changeset.user
        if changeset_user is None:
            raise AssertionError('Changeset user must be set')
        user_name = changeset_user.display_name
        user_avatar = changeset_user.avatar_url
    else:
        user_name = None
        user_avatar = None
    params_bounds: list[SharedBounds] = [None] * len(changeset.bounds)  # pyright: ignore[reportAssignmentType]
    i: cython.int
    for i, cb in enumerate(changeset.bounds):
        bounds = cb.bounds.bounds
        params_bounds[i] = SharedBounds(
            min_lon=bounds[0],
            min_lat=bounds[1],
            max_lon=bounds[2],
            max_lat=bounds[3],
        )
    return RenderChangesetData(
        id=changeset.id,
        bounds=params_bounds,
        user_name=user_name,
        user_avatar=user_avatar,
        closed=changeset.closed_at is not None,
        timeago=timeago(changeset.closed_at if (changeset.closed_at is not None) else changeset.created_at, html=True),
        comment=changeset.tags.get('comment'),
        num_comments=num_comments,
    )
