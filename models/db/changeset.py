from collections.abc import Sequence
from datetime import datetime
from typing import Self

import anyio
from shapely.geometry import Polygon, box
from shapely.geometry.base import BaseGeometry
from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.db.base import _DEFAULT_FIND_LIMIT, Base
from models.db.created_at import CreatedAt
from models.db.updated_at import UpdatedAt
from models.db.user import User
from models.geometry_type import PolygonType
from utils import utcnow

# TODO: 0.7 180th meridian ?


class Changeset(Base.Sequential, CreatedAt, UpdatedAt):
    __tablename__ = 'changeset'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(back_populates='changesets', lazy='raise')
    tags: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)  # TODO: normalize unicode, check unicode

    # defaults
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    boundary: Mapped[Polygon | None] = mapped_column(PolygonType, nullable=True, default=None)

    # relationships (nested imports to avoid circular imports)
    from changeset_comment import ChangesetComment
    from changeset_subscription import ChangesetSubscription
    from element import Element

    changeset_comments: Mapped[Sequence[ChangesetComment]] = relationship(
        back_populates='changeset',
        order_by='asc(ChangesetComment.created_at)',
        lazy='raise',
    )
    changeset_subscription_users: Mapped[Sequence[User]] = relationship(
        secondary=ChangesetSubscription,
        lazy='raise',
    )
    elements: Mapped[Sequence[Element]] = relationship(
        back_populates='changeset',
        order_by='asc(Element.id)',
        lazy='raise',
    )

    @property
    def max_size(self) -> int:
        """
        Get the maximum size for this changeset
        """

        return self.user.changeset_max_size

    # TODO: SQL
    @classmethod
    async def find_many_by_query_with_(
        cls,
        ids: Sequence[SequentialId] | None = None,
        user_id: SequentialId | None = None,
        time_closed_after: datetime | None = None,
        time_created_before: datetime | None = None,
        open: bool | None = None,
        geometry: Polygon | None = None,
        sort: dict | None = None,
        limit: int | None = _DEFAULT_FIND_LIMIT,
    ) -> Sequence[Self]:
        pipeline = [
            # find all the documents that match all the filters
            {
                '$match': {
                    **({'_id': {'$in': ids}} if ids else {}),
                    **({'user_id': user_id} if user_id else {}),
                    **({'closed_at': {'$gte': time_closed_after}} if time_closed_after else {}),
                    **({'created_at': {'$lt': time_created_before}} if time_created_before else {}),
                    **({'closed_at': None} if open is True else {}),
                    **({'closed_at': {'$ne': None}} if open is False else {}),
                    **({'boundary': {'$geoIntersects': {'$geometry': mapping_mongo(geometry)}}} if geometry else {}),
                }
            },
            # lookup comments count
            {
                '$lookup': {
                    'from': ChangesetComment._collection_name(),
                    'localField': '_id',
                    'foreignField': 'changeset_id',
                    'as': 'comments_',
                }
            },
            {'$set': {'comments_count_': {'$size': '$comments_'}}},
            {'$unset': 'comments_'},
        ]

        cursor = cls._collection().aggregate(pipeline)
        if sort:
            cursor = cursor.sort(sort)
        if limit:
            cursor = cursor.limit(limit)
        result = []
        async for doc in cursor:
            result.append(cls.model_validate(doc))
        return result

    @classmethod
    async def find_one_by_id_with_(
        cls,
        changeset_id: SequentialId,
        *,
        comment_sort: dict | None = None,
        comment_limit: int | None = 0,
        element_sort: dict | None = None,
        element_limit: int | None = 0,
    ) -> Self | None:
        changeset: Changeset = None
        comments_count: NonNegativeInt = None
        comments: Sequence[ChangesetComment] | None = None
        elements: Sequence[Element] | None = None

        async def assign_changeset(cancel_scope: anyio.CancelScope) -> None:
            nonlocal changeset
            changeset = await cls.find_one_by_id(changeset_id)

            if not changeset:
                # small optimization, cancel other queries if changeset is not found
                cancel_scope.cancel()

        async def assign_comments() -> None:
            nonlocal comments
            nonlocal comments_count
            if comment_limit != 0:
                comments = await ChangesetComment.find_many_by_changeset_id(
                    changeset_id, sort=comment_sort, limit=comment_limit
                )
                comments_count = len(comments)
            else:
                comments_count = await ChangesetComment.count_by_changeset_id(changeset_id)

        async def assign_elements() -> None:
            if element_limit != 0:
                nonlocal elements
                elements = await Element.find_many_by_changeset_id(changeset_id, sort=element_sort, limit=element_limit)

        async with anyio.create_task_group() as tg:
            tg.start_soon(assign_changeset, tg.cancel_scope)
            tg.start_soon(assign_comments)
            tg.start_soon(assign_elements)

        if not changeset:
            return None

        changeset.comments_count_ = comments_count
        changeset.comments_ = comments
        changeset.elements_ = elements
        return changeset

    # TODO: master class for created_at + updated_at?
    def update_batch(self, filter_ex: dict | None = None) -> UpdateOne:
        return super().update_batch({'updated_at': self.updated_at, **(filter_ex or {})})

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

        self.closed_at = now or utcnow()
        return True

    def union_boundary(self, geometry: BaseGeometry) -> None:
        if not self.boundary:
            self.boundary = box(*geometry.bounds)
        else:
            self.boundary = box(*self.boundary.union(geometry).bounds)
