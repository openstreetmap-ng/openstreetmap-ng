from datetime import datetime
from functools import cached_property
from typing import TYPE_CHECKING

from shapely import Polygon, box
from shapely.geometry.base import BaseGeometry
from sqlalchemy import ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.updated_at_mixin import UpdatedAtMixin
from app.models.db.user import User
from app.models.geometry import PolygonType
from app.models.user_role import UserRole

if TYPE_CHECKING:
    from app.models.db.changeset_comment import ChangesetComment

# TODO: 0.7 180th meridian ?


class Changeset(Base.Sequential, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = 'changeset'

    user_id: Mapped[int | None] = mapped_column(ForeignKey(User.id), nullable=True)
    user: Mapped[User | None] = relationship(init=False, lazy='raise')
    tags: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    # TODO: normalize unicode, check unicode, check length

    # defaults
    # TODO: test updated at optimistic
    closed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(True),
        init=False,
        nullable=True,
        server_default=None,
    )
    size: Mapped[int] = mapped_column(
        Integer,
        init=False,
        nullable=False,
        server_default='0',
    )
    bounds: Mapped[Polygon | None] = mapped_column(
        PolygonType,
        init=False,
        nullable=True,
        server_default=None,
    )

    __table_args__ = ()

    # runtime
    comments: list['ChangesetComment'] | None = None

    @cached_property
    def max_size(self) -> int:
        """
        Get the maximum size for this changeset.
        """
        return UserRole.get_changeset_max_size(self.user.roles)

    def increase_size(self, n: int) -> bool:
        """
        Increase the changeset size by n.

        Returns True if the size was increased successfully.
        """
        if n < 0:
            raise ValueError('n must be non-negative')

        new_size = self.size + n
        if new_size > self.max_size:
            return False

        self.size = new_size
        return True

    def auto_close_on_size(self) -> bool:
        """
        Close the changeset if it is open and reaches the size limit.

        Returns True if the changeset was closed.
        """
        if self.closed_at is not None:
            return False
        if self.size < self.max_size:
            return False
        self.closed_at = func.statement_timestamp()
        return True

    def union_bounds(self, geometry: BaseGeometry) -> None:
        """
        Update the changeset bounds to include the given geometry.
        """
        if self.bounds is None:
            self.bounds = box(*geometry.bounds)
        else:
            self.bounds = box(*self.bounds.union(geometry).bounds)
