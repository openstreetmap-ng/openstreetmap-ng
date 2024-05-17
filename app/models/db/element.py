from datetime import datetime
from typing import TYPE_CHECKING

from shapely import Point
from sqlalchemy import (
    BigInteger,
    Boolean,
    Enum,
    ForeignKey,
    Identity,
    Index,
    PrimaryKeyConstraint,
    and_,
    func,
    null,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.lib.updating_cached_property import updating_cached_property
from app.models.db.base import Base
from app.models.db.changeset import Changeset
from app.models.element_ref import ElementRef, VersionedElementRef
from app.models.element_type import ElementType
from app.models.geometry import PointType

if TYPE_CHECKING:
    from app.models.db.element_member import ElementMember


class Element(Base.NoID):
    __tablename__ = 'element'

    sequence_id: Mapped[int] = mapped_column(BigInteger, Identity(minvalue=1), init=False, nullable=False)
    changeset_id: Mapped[int] = mapped_column(ForeignKey(Changeset.id), nullable=False)
    changeset: Mapped[Changeset] = relationship(init=False, lazy='raise', innerjoin=True)
    type: Mapped[ElementType] = mapped_column(Enum('node', 'way', 'relation', name='element_type'), nullable=False)
    id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tags: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    point: Mapped[Point | None] = mapped_column(PointType, nullable=True)

    # defaults
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(True),
        init=False,
        nullable=False,
        server_default=func.statement_timestamp(),
    )
    next_sequence_id: Mapped[int | None] = mapped_column(
        BigInteger,
        init=False,
        nullable=True,
        server_default=None,
    )

    # runtime
    members: list['ElementMember'] | None = None

    __table_args__ = (
        PrimaryKeyConstraint(sequence_id, name='element_pkey'),
        Index('element_changeset_idx', changeset_id),
        Index('element_version_idx', type, id, version),
        Index('element_current_idx', type, id, next_sequence_id, postgresql_include=('sequence_id',)),
        Index(
            'element_node_point_idx',
            point,
            postgresql_where=and_(type == 'node', visible == true(), next_sequence_id == null()),
            postgresql_using='gist',
        ),
    )

    @updating_cached_property('id')
    def element_ref(self) -> ElementRef:
        return ElementRef(self.type, self.id)

    @updating_cached_property('id')
    def versioned_ref(self) -> VersionedElementRef:
        return VersionedElementRef(self.type, self.id, self.version)

    @updating_cached_property('members')
    def members_element_refs(self) -> frozenset[ElementRef]:
        return frozenset(ElementRef(member.type, member.id) for member in self.members)
