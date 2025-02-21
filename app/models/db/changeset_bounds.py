from typing import TypedDict

from shapely import Polygon

from app.models.db.changeset import ChangesetId


class ChangesetBounds(TypedDict):
    changeset_id: ChangesetId
    bounds: Polygon
