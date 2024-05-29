from collections.abc import Sequence

from app.lib.jinja_env import timeago
from app.models.db.changeset import Changeset
from app.models.msgspec.leaflet import ChangesetLeaflet


class LeafletChangesetMixin:
    @staticmethod
    def encode_changesets(changesets: Sequence[Changeset]) -> Sequence[ChangesetLeaflet]:
        """
        Format changesets into a minimal structure, suitable for Leaflet rendering.
        """
        return tuple(
            ChangesetLeaflet(
                id=changeset.id,
                geom=changeset.bounds.bounds,
                user_name=changeset.user.display_name if (changeset.user_id is not None) else None,
                user_avatar=changeset.user.avatar_url if (changeset.user_id is not None) else None,
                closed=changeset.closed_at is not None,
                timeago=timeago(
                    changeset.closed_at if (changeset.closed_at is not None) else changeset.created_at,
                    html=True,
                ),
                comment=changeset.tags.get('comment'),
                num_comments=changeset.num_comments,
            )
            for changeset in changesets
        )
