from datetime import datetime
from typing import TYPE_CHECKING

import anyio
from shapely.geometry import Polygon, box
from shapely.geometry.base import BaseGeometry
from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.config import APP_URL
from src.models.db.base import Base
from src.models.db.created_at_mixin import CreatedAtMixin
from src.models.db.updated_at_mixin import UpdatedAtMixin
from src.models.db.user import User
from src.models.geometry_type import PolygonType

# TODO: 0.7 180th meridian ?


class Changeset(Base.Sequential, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = 'changeset'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(lazy='raise')
    tags: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    # TODO: normalize unicode, check unicode, check length

    # defaults
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    boundary: Mapped[Polygon | None] = mapped_column(PolygonType, nullable=True, default=None)

    # relationships (avoid circular imports)
    if TYPE_CHECKING:
        from src.models.db.element import Element

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

        return self.user.changeset_max_size

    async def resolve_comments_rich_text(self) -> None:
        """
        Resolve rich text for all comments.
        """

        async with anyio.create_task_group() as tg:
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

        if self.closed_at:
            return False
        if self._size < self.max_size:
            return False

        self.closed_at = now or func.now()
        return True

    def union_boundary(self, geometry: BaseGeometry) -> None:
        if not self.boundary:
            self.boundary = box(*geometry.bounds)
        else:
            self.boundary = box(*self.boundary.union(geometry).bounds)
