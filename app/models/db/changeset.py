from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING

from shapely import Polygon, box
from shapely.geometry.base import BaseGeometry
from sqlalchemy import ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import APP_URL
from app.lib.tag_stylize import tag_stylize
from app.lib.translation import t
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.user import User
from app.models.geometry import PolygonType
from app.models.tag_style import TagStyleCollection
from app.models.user_role import UserRole

if TYPE_CHECKING:
    from app.models.db.changeset_comment import ChangesetComment
    from app.models.db.element import Element

# TODO: 0.7 180th meridian ?


class Changeset(Base.Sequential, CreatedAtMixin):
    __tablename__ = 'changeset'

    user_id: Mapped[int | None] = mapped_column(ForeignKey(User.id), nullable=True)
    user: Mapped[User | None] = relationship(init=False, lazy='joined', innerjoin=True)
    tags: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    # TODO: normalize unicode, check unicode, check length

    # defaults
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(True),
        init=False,
        nullable=False,
        server_default=func.statement_timestamp(),
        onupdate=func.statement_timestamp(),  # instead of server_default, optimistic update overrides it
    )
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

    # relationships (avoid circular imports)
    elements: Mapped[list['Element']] = relationship(
        back_populates='changeset',
        order_by='Element.id.asc()',
        lazy='raise',
        init=False,
    )

    # runtime
    comments: list['ChangesetComment'] | None = None

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

    # @property
    # def comment(self) -> str:
    #     """
    #     Get the comment for this changeset
    #     """
    #     result = self.tags.get('comment')
    #     if result is not None:
    #         return result
    #     return t('browse.no_comment')

    @property
    def tags_stylized_map(self) -> dict[str, TagStyleCollection]:
        """
        Get the stylized tags for this changeset
        """
        tags = [(key, TagStyleCollection(key, value)) for key, value in self.tags.items()]
        tags.sort()
        result = dict(tags)

        # TODO: remove after testing
        # result['colour'] = TagStyleCollection('colour', 'red;blue')
        # result['email'] = TagStyleCollection('email', '1@example.com;2@example.com')
        # result['something:email'] = TagStyleCollection('something:email', '1@example.com;2@example.com')
        # result['phone'] = TagStyleCollection('phone', '+1-234-567-8901')
        # result['amenity'] = TagStyleCollection('amenity', 'bench')

        tag_stylize(result.values())
        return result

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
        """
        Update the changeset bounds to include the given geometry.
        """

        if self.bounds is None:
            self.bounds = box(*geometry.bounds)
        else:
            self.bounds = box(*self.bounds.union(geometry).bounds)
