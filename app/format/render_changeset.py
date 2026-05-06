import cython
from shapely import measurement

from app.models.db.changeset import Changeset
from app.models.db.user import user_proto
from app.models.proto.changeset_pb2 import GetMapResponse


class RenderChangesetMixin:
    @staticmethod
    def encode_changesets(changesets: list[Changeset]):
        """Format changesets into a minimal structure, suitable for map rendering."""
        response = GetMapResponse()
        for changeset in changesets:
            _encode_changeset(response.changesets.add(), changeset)
        return response


@cython.cfunc
def _encode_changeset(result: GetMapResponse.Changeset, changeset: Changeset):
    bounds = changeset.get('bounds')
    bboxes: list[list[float]]
    bboxes = measurement.bounds(bounds.geoms).tolist() if bounds is not None else []  # type: ignore

    closed_at = changeset['closed_at']
    status_changed_at = int((closed_at or changeset['created_at']).timestamp())
    result.id = changeset['id']
    if (user := user_proto(changeset.get('user'))) is not None:
        result.user.CopyFrom(user)
    for bbox in bboxes:
        bound = result.bounds.add()
        bound.min_lon = bbox[0]
        bound.min_lat = bbox[1]
        bound.max_lon = bbox[2]
        bound.max_lat = bbox[3]
    result.closed = closed_at is not None
    result.status_changed_at = status_changed_at
    if (comment := changeset['tags'].get('comment')) is not None:
        result.comment = comment
    result.num_create = changeset['num_create']
    result.num_modify = changeset['num_modify']
    result.num_delete = changeset['num_delete']
    result.num_comments = changeset['num_comments']  # pyright: ignore [reportTypedDictNotRequiredAccess]
