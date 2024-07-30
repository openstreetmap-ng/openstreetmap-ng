from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal, get_args

from shapely import Point
from sqlalchemy import (
    BigInteger,
    Boolean,
    Enum,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    and_,
    null,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base
from app.models.db.changeset import Changeset
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.element import ElementId, ElementType
from app.models.geometry import PointType

if TYPE_CHECKING:
    from app.models.db.element_member import ElementMember


class Element(Base.NoID, CreatedAtMixin):
    __tablename__ = 'element'

    sequence_id: Mapped[int] = mapped_column(BigInteger, init=False, nullable=False)
    changeset_id: Mapped[int] = mapped_column(ForeignKey(Changeset.id), nullable=False)
    type: Mapped[ElementType] = mapped_column(Enum(*get_args(ElementType), name='element_type'), nullable=False)
    id: Mapped[ElementId] = mapped_column(BigInteger, nullable=False)
    version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tags: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    point: Mapped[Point | None] = mapped_column(PointType, nullable=True)
    next_sequence_id: Mapped[int | None] = mapped_column(BigInteger, init=False, nullable=True)

    # runtime
    members: Sequence['ElementMember'] | None = None
    user_id: int | None = None
    user_display_name: str | None = None
    delete_if_unused: Literal[True] | None = None

    __table_args__ = (
        PrimaryKeyConstraint(sequence_id, name='element_pkey'),
        Index('element_changeset_idx', changeset_id),
        Index('element_version_idx', type, id, version),
        Index('element_current_idx', type, id, next_sequence_id, sequence_id),
        Index(
            'element_node_point_idx',
            point,
            postgresql_where=and_(type == 'node', visible == true(), next_sequence_id == null()),
            postgresql_using='gist',
        ),
    )
