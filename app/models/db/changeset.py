from datetime import datetime
from typing import TYPE_CHECKING

from anyio import create_task_group
from shapely import Polygon, box
from shapely.geometry.base import BaseGeometry
from sqlalchemy import ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import APP_URL
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.user import User
from app.models.geometry import PolygonType
from app.models.user_role import UserRole

if TYPE_CHECKING:
    from app.models.db.element import Element

# TODO: 0.7 180th meridian ?


class Changeset(Base.Sequential, CreatedAtMixin):
    __tablename__ = 'changeset'

    user_id: Mapped[int | None] = mapped_column(ForeignKey(User.id), nullable=True)
    user: Mapped[User | None] = relationship(lazy='raise')
    tags: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    # TODO: normalize unicode, check unicode, check length

    # defaults
    # updated_at without server_onupdate (optimistic update manages it)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(True), nullable=False, server_default=func.statement_timestamp()
    )
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(True), nullable=True, server_default=None)
    size: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')
    bounds: Mapped[Polygon | None] = mapped_column(PolygonType, nullable=True, server_default=None)

    # relationships (avoid circular imports)
    elements: Mapped[list['Element']] = relationship(
        back_populates='changeset',
        order_by='Element.id.asc()',
        lazy='raise',
    )

    @property
    def permalink(self) -> str:
        """
        Get the changeset's permalink.

        >>> changeset.permalink
        'https://www.openstreetmap.org/changeset/123456'
        """

        return f'{APP_URL}/changeset/{self.id}'

    @property
    def max_size(self) -> int:
        """
        Get the maximum size for this changeset
        """

        return UserRole.get_changeset_max_size(self.user.roles)

    async def resolve_comments_rich_text(self) -> None:
        """
        Resolve rich text for all comments.
        """

        async with create_task_group() as tg:
            for comment in self.comments:
                tg.start_soon(comment.resolve_rich_text)

    def increase_size(self, n: int) -> bool:
        """
        Increase the changeset size by n.

        Returns `True` if the size was increased successfully.
        """

        if n < 0:
            raise ValueError('n must be non-negative')

        new_size = self.size + n
        if new_size > self.max_size:
            return False

        self.size = new_size
        return True

    def auto_close_on_size(self, *, now: datetime | None = None) -> bool:
        """
        Close the changeset if it is open and reaches the size limit.

        Returns `True` if the changeset was closed.
        """

        if self.closed_at is not None:
            return False
        if self._size < self.max_size:
            return False

        self.closed_at = now or func.statement_timestamp()
        return True

    def union_bounds(self, geometry: BaseGeometry) -> None:
        if self.bounds is None:
            self.bounds = box(*geometry.bounds)
        else:
            self.bounds = box(*self.bounds.union(geometry).bounds)
