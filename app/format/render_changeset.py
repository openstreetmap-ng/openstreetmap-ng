import cython
from shapely import measurement

from app.models.db.changeset import Changeset
from app.models.db.user import user_proto
from app.models.proto.changeset_pb2 import RenderChangesetsData
from app.models.proto.shared_pb2 import Bounds


class RenderChangesetMixin:
    @staticmethod
    def encode_changesets(changesets: list[Changeset]):
        """Format changesets into a minimal structure, suitable for map rendering."""
        return RenderChangesetsData(changesets=list(map(_encode_changeset, changesets)))


@cython.cfunc
def _encode_changeset(changeset: Changeset):
    bounds = changeset.get('bounds')
    bboxes: list[list[float]]
    bboxes = measurement.bounds(bounds.geoms).tolist() if bounds is not None else []  # type: ignore
    params_bounds = [
        Bounds(min_lon=bbox[0], min_lat=bbox[1], max_lon=bbox[2], max_lat=bbox[3])
        for bbox in bboxes
    ]

    closed_at = changeset['closed_at']
    status_changed_at = int((closed_at or changeset['created_at']).timestamp())

    return RenderChangesetsData.Changeset(
        id=changeset['id'],
        user=user_proto(changeset.get('user')),
        bounds=params_bounds,
        closed=closed_at is not None,
        status_changed_at=status_changed_at,
        comment=changeset['tags'].get('comment'),
        num_create=changeset['num_create'],
        num_modify=changeset['num_modify'],
        num_delete=changeset['num_delete'],
        num_comments=changeset['num_comments'],  # pyright: ignore [reportTypedDictNotRequiredAccess]
    )
