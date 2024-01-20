from collections.abc import Sequence
from typing import TYPE_CHECKING

from shapely import Point
from sqlalchemy import ARRAY, ColumnElement, Enum, ForeignKey, Integer, Unicode
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.libc.storage.base import STORAGE_KEY_MAX_LENGTH
from app.limits import TRACE_TAG_MAX_LENGTH, TRACE_TAGS_LIMIT
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.user import User
from app.models.geometry_type import PointType
from app.models.scope import ExtendedScope
from app.models.trace_visibility import TraceVisibility


class Trace(Base.Sequential, CreatedAtMixin):
    __tablename__ = 'trace'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(lazy='raise')
    name: Mapped[str] = mapped_column(Unicode, nullable=False)
    description: Mapped[str] = mapped_column(Unicode, nullable=False)
    visibility: Mapped[TraceVisibility] = mapped_column(Enum(TraceVisibility), nullable=False)

    size: Mapped[int] = mapped_column(Integer, nullable=False)
    start_point: Mapped[Point] = mapped_column(PointType, nullable=False)
    file_id: Mapped[str] = mapped_column(Unicode(STORAGE_KEY_MAX_LENGTH), nullable=False)
    image_id: Mapped[str] = mapped_column(Unicode(STORAGE_KEY_MAX_LENGTH), nullable=False)
    icon_id: Mapped[str] = mapped_column(Unicode(STORAGE_KEY_MAX_LENGTH), nullable=False)

    # defaults
    tags: Mapped[list[str]] = mapped_column(ARRAY(Unicode), nullable=False, default=())

    # relationships (avoid circular imports)
    if TYPE_CHECKING:
        from app.models.db.trace_point import TracePoint

    # TODO: cascade delete + files delete
    # TODO: limit size points
    points: Mapped[list['TracePoint']] = relationship(
        back_populates='trace',
        order_by='(TracePoint.track_idx.asc(), TracePoint.captured_at.asc())',
        lazy='raise',
    )

    @validates('tags')
    def validate_tags(self, _: str, value: Sequence[str]):
        if len(value) > TRACE_TAGS_LIMIT:
            raise ValueError('Too many tags')
        return value

    @property
    def tag_string(self) -> str:
        return ', '.join(self.tags)

    @tag_string.setter
    def tag_string(self, s: str) -> None:
        if ',' in s:  # noqa: SIM108
            tags = s.split(',')
        else:
            # do as before for backwards compatibility
            # BUG: this produces weird behavior: 'a b, c' -> ['a b', 'c']; 'a b' -> ['a', 'b']
            tags = s.split()

        tags = (t.strip()[:TRACE_TAG_MAX_LENGTH].strip() for t in tags)
        tags = (t for t in tags if t)
        self.tags = tuple(set(tags))

    @hybrid_property
    def linked_to_user_in_api(self) -> bool:
        return self.visibility == TraceVisibility.identifiable

    @linked_to_user_in_api.inplace.expression
    @classmethod
    def _linked_to_user_in_api_expression(cls) -> ColumnElement[bool]:
        return cls.visibility == TraceVisibility.identifiable

    @hybrid_property
    def linked_to_user_on_site(self) -> bool:
        return self.visibility in (TraceVisibility.identifiable, TraceVisibility.public)

    @linked_to_user_on_site.inplace.expression
    @classmethod
    def _linked_to_user_on_site_expression(cls) -> ColumnElement[bool]:
        return cls.visibility.in_((TraceVisibility.identifiable, TraceVisibility.public))

    @hybrid_property
    def timestamps_via_api(self) -> bool:
        return self.visibility in (TraceVisibility.identifiable, TraceVisibility.trackable)

    @timestamps_via_api.inplace.expression
    @classmethod
    def _timestamps_via_api_expression(cls) -> ColumnElement[bool]:
        return cls.visibility.in_((TraceVisibility.identifiable, TraceVisibility.trackable))

    @hybrid_method
    def visible_to(self, user: User | None, scopes: Sequence[ExtendedScope]) -> bool:
        if user and ExtendedScope.read_gpx in scopes:
            return self.linked_to_user_on_site or (self.user_id == user.id)
        else:
            return self.linked_to_user_on_site

    @visible_to.expression
    @classmethod
    def visible_to(cls, user: User | None, scopes: Sequence[ExtendedScope]) -> ColumnElement[bool]:
        if user and ExtendedScope.read_gpx in scopes:
            return cls.linked_to_user_on_site | (cls.user_id == user.id)
        else:
            return cls.linked_to_user_on_site
