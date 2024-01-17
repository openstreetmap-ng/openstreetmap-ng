from collections.abc import Sequence
from datetime import datetime

from shapely import Point
from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from src.lib_cython.updating_cached_property import updating_cached_property
from src.models.db.base import Base
from src.models.db.changeset import Changeset
from src.models.db.created_at_mixin import CreatedAtMixin
from src.models.db.user import User
from src.models.element_member import ElementMemberRef
from src.models.element_member_type import ElementMemberRefType
from src.models.element_type import ElementType
from src.models.geometry_type import PointType
from src.models.typed_element_ref import TypedElementRef
from src.models.versioned_element_ref import VersionedElementRef


class Element(Base.Sequential, CreatedAtMixin):
    __tablename__ = 'element'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(lazy='raise')
    changeset_id: Mapped[int] = mapped_column(ForeignKey(Changeset.id), nullable=False)
    changeset: Mapped[Changeset] = relationship(back_populates='elements', lazy='raise')
    type: Mapped[ElementType] = mapped_column(Enum(ElementType), nullable=False)
    typed_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tags: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    point: Mapped[Point | None] = mapped_column(PointType, nullable=True)
    members: Mapped[list[ElementMemberRef]] = mapped_column(ElementMemberRefType, nullable=False)

    # defaults
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    __table_args__ = (UniqueConstraint(type, typed_id, version),)

    @validates('typed_id')
    def validate_typed_id(self, _: str, value: int):
        if value <= 0:
            raise ValueError('typed_id must be positive')
        return value

    @validates('members')
    def validate_members(self, _: str, value: Sequence[ElementMemberRef]):
        if any(member.typed_id <= 0 for member in value):
            raise ValueError('members typed_id must be positive')
        return value

    @updating_cached_property('typed_id')
    def typed_ref(self) -> TypedElementRef:
        return TypedElementRef(type=self.type, typed_id=self.typed_id)

    @updating_cached_property('typed_id')
    def versioned_ref(self) -> VersionedElementRef:
        return VersionedElementRef(type=self.type, typed_id=self.typed_id, version=self.version)
