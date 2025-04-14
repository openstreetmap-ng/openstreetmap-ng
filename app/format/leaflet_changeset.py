import cython
from shapely import measurement

from app.models.db.changeset import Changeset
from app.models.db.user import user_avatar_url
from app.models.proto.shared_pb2 import RenderChangesetsData, SharedBounds


class LeafletChangesetMixin:
    @staticmethod
    def encode_changesets(changesets: list[Changeset]) -> RenderChangesetsData:
        """Format changesets into a minimal structure, suitable for map rendering."""
        return RenderChangesetsData(
            changesets=[_encode_changeset(changeset) for changeset in changesets]
        )


@cython.cfunc
def _encode_changeset(changeset: Changeset):
    params_user = (
        RenderChangesetsData.Changeset.User(
            name=changeset_user['display_name'],
            avatar_url=user_avatar_url(changeset_user),
        )
        if (changeset_user := changeset.get('user')) is not None
        else None
    )

    bounds = changeset.get('bounds')
    bboxes: list[list[float]]
    bboxes = measurement.bounds(bounds.geoms).tolist() if bounds is not None else []  # type: ignore
    params_bounds = [
        SharedBounds(
            min_lon=bbox[0],
            min_lat=bbox[1],
            max_lon=bbox[2],
            max_lat=bbox[3],
        )
        for bbox in bboxes
    ]

    closed_at = changeset['closed_at']
    timeago_date = closed_at or changeset['created_at']
    timeago_html = (
        f'<time datetime="{timeago_date.isoformat()}" data-style="long"></time>'
    )

    return RenderChangesetsData.Changeset(
        id=changeset['id'],
        user=params_user,
        bounds=params_bounds,
        closed=closed_at is not None,
        timeago=timeago_html,
        comment=changeset['tags'].get('comment'),
        num_create=changeset['num_create'],
        num_modify=changeset['num_modify'],
        num_delete=changeset['num_delete'],
        num_comments=changeset['num_comments'],  # pyright: ignore [reportTypedDictNotRequiredAccess]
    )
