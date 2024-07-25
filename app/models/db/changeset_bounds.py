from shapely import Polygon
from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base
from app.models.db.changeset import Changeset
from app.models.geometry import PolygonType


class ChangesetBounds(Base.ZID):
    __tablename__ = 'changeset_bounds'

    changeset_id: Mapped[int] = mapped_column(ForeignKey(Changeset.id, ondelete='CASCADE'), init=False, nullable=False)
    bounds: Mapped[Polygon] = mapped_column(PolygonType, nullable=False)

    __table_args__ = (
        Index('changeset_bounds_id_idx', changeset_id),
        Index('changeset_bounds_bounds_idx', bounds, postgresql_using='gist'),
    )
