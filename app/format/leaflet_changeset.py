from collections.abc import Iterable

import cython

from app.models.db.changeset import Changeset
from app.models.proto.shared_pb2 import RenderChangesetsData, SharedBounds


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
        params_user = RenderChangesetsData.Changeset.User(
            name=changeset_user.display_name,
            avatar_url=changeset_user.avatar_url,
        )
    else:
        params_user = None
    params_bounds: list[SharedBounds] = [None] * len(changeset.bounds)  # type: ignore
    i: cython.int
    for i, cb in enumerate(changeset.bounds):
        bounds = cb.bounds.bounds
        params_bounds[i] = SharedBounds(
            min_lon=bounds[0],
            min_lat=bounds[1],
            max_lon=bounds[2],
            max_lat=bounds[3],
        )
    timeago_date = changeset.closed_at if (changeset.closed_at is not None) else changeset.created_at
    timeago_html = f'<time datetime="{timeago_date.isoformat()}" data-style="long"></time>'
    return RenderChangesetsData.Changeset(
        id=changeset.id,
        user=params_user,
        bounds=params_bounds,
        closed=changeset.closed_at is not None,
        timeago=timeago_html,
        comment=changeset.tags.get('comment'),
        num_comments=num_comments,
    )
