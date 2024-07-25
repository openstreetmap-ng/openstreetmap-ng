from collections.abc import Iterable

import cython

from app.lib.jinja_env import timeago
from app.models.db.changeset import Changeset
from app.models.msgspec.leaflet import ChangesetLeaflet


class LeafletChangesetMixin:
    @staticmethod
    def encode_changesets(changesets: Iterable[Changeset]) -> tuple[ChangesetLeaflet, ...]:
        """
        Format changesets into a minimal structure, suitable for Leaflet rendering.
        """
        return tuple(_encode_changeset(changeset) for changeset in changesets)


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
    return ChangesetLeaflet(
        id=changeset.id,
        geom=tuple(cb.bounds.bounds for cb in changeset.bounds),
        user_name=user_name,
        user_avatar=user_avatar,
        closed=changeset.closed_at is not None,
        timeago=timeago(changeset.closed_at if (changeset.closed_at is not None) else changeset.created_at, html=True),
        comment=changeset.tags.get('comment'),
        num_comments=num_comments,
    )
