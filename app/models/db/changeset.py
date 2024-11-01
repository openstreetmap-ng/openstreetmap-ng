from datetime import datetime
from functools import cached_property
from typing import TYPE_CHECKING

from shapely import Polygon
from sqlalchemy import ForeignKey, Index, Integer, and_, func, null
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.lib.user_role_limits import UserRoleLimits
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.updated_at_mixin import UpdatedAtMixin
from app.models.db.user import User
from app.models.geometry import PolygonType

if TYPE_CHECKING:
    from app.models.db.changeset_bounds import ChangesetBounds
    from app.models.db.changeset_comment import ChangesetComment


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
    bounds: Mapped[list['ChangesetBounds']] = relationship(
        init=False,
        lazy='selectin',
        cascade='save-update, delete, delete-orphan',
    )
    union_bounds: Mapped[Polygon | None] = mapped_column(
        PolygonType,
        init=False,
        nullable=True,
        server_default=None,
    )

    # runtime
    num_comments: int | None = None
    comments: list['ChangesetComment'] | None = None

    __table_args__ = (
        Index('changeset_user_idx', user_id, 'id', postgresql_where=user_id != null()),
        Index('changeset_created_at_idx', 'created_at'),
        Index('changeset_closed_at_idx', closed_at, postgresql_where=closed_at != null()),
        Index('changeset_open_idx', 'updated_at', postgresql_where=closed_at == null()),
        # TODO: optimize out empty changesets
        Index('changeset_empty_idx', closed_at, postgresql_where=and_(closed_at != null(), size == 0)),
        Index(
            'changeset_union_bounds_idx',
            union_bounds,
            postgresql_where=union_bounds != null(),
            postgresql_using='gist',
        ),
    )

    @cached_property
    def max_size(self) -> int:
        """
        Get the maximum size for this changeset.
        """
        user = self.user
        if user is None:
            raise AssertionError('Changeset user must be set')
        return UserRoleLimits.get_changeset_max_size(user.roles)

    def set_size(self, new_size: int) -> bool:
        """
        Change the changeset size.

        Returns True if the size was changed successfully.
        """
        if self.size >= new_size:
            raise ValueError('New size must be greater than the current size')
        if new_size > self.max_size:
            return False
        self.size = new_size
        return True

    def auto_close_on_size(self, now: datetime | None = None) -> bool:
        """
        Close the changeset if it is open and reaches the size limit.

        Returns True if the changeset was closed.
        """
        if self.closed_at is not None:
            return False
        if self.size < self.max_size:
            return False
        self.closed_at = func.statement_timestamp() if (now is None) else now
        return True
