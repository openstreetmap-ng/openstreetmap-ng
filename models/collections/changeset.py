from datetime import datetime
from typing import Annotated, Self, Sequence

import anyio
from pydantic import Field, NonNegativeInt, model_validator
from pymongo import UpdateOne
from shapely.geometry import Polygon, box
from shapely.geometry.base import BaseGeometry

from geoutils import mapping_mongo
from lib.auth import Auth
from models.collections.base import _DEFAULT_FIND_LIMIT
from models.collections.base_sequential import BaseSequential, SequentialId
from models.collections.changeset_comment import ChangesetComment
from models.collections.element import Element
from models.geometry import PolygonGeometry
from models.str import EmptyStr255
from models.user_role import UserRole
from utils import utcnow


class Changeset(BaseSequential):
    user_id: Annotated[SequentialId, Field(frozen=True)]
    tags: dict[EmptyStr255, EmptyStr255]

    # defaults
    created_at: Annotated[datetime, Field(frozen=True, default_factory=utcnow)]
    updated_at: Annotated[datetime, Field(default_factory=utcnow)]  # TODO: automate
    closed_at: datetime | None = None
    size: NonNegativeInt = 0
    boundary: PolygonGeometry | None = None
    # TODO: 0.7 180th meridian

    comments_count_: Annotated[NonNegativeInt | None, Field(exclude=True)] = None
    comments_: Annotated[tuple[ChangesetComment, ...] | None, Field(exclude=True)] = None
    elements_: Annotated[tuple[Element, ...] | None, Field(exclude=True)] = None

    @model_validator(mode='after')
    def validate_closed_at(self) -> Self:
        if self.closed_at and self.closed_at < self.created_at:
            raise ValueError(f'{self.__class__.__qualname__} cannot be closed before it was opened')
        return self

    @model_validator(mode='after')
    def validate_boundary(self) -> Self:
        if bool(self.boundary) == bool(self.size):
            raise ValueError(f'{self.__class__.__qualname__} must have a boundary if and only if it has a size')
        return self

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
            limit: int | None = _DEFAULT_FIND_LIMIT) -> Sequence[Self]:
        pipeline = [
            # find all the documents that match all the filters
            {'$match': {
                **({'_id': {'$in': ids}} if ids else {}),
                **({'user_id': user_id} if user_id else {}),
                **({'closed_at': {'$gte': time_closed_after}} if time_closed_after else {}),
                **({'created_at': {'$lt': time_created_before}} if time_created_before else {}),
                **({'closed_at': None} if open is True else {}),
                **({'closed_at': {'$ne': None}} if open is False else {}),
                **({'boundary': {'$geoIntersects': {'$geometry': mapping_mongo(geometry)}}} if geometry else {}),
            }},

            # lookup comments count
            {'$lookup': {
                'from': ChangesetComment._collection_name(),
                'localField': '_id',
                'foreignField': 'changeset_id',
                'as': 'comments_'
            }},
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
    async def find_one_by_id_with_(cls,
                                   changeset_id: SequentialId, *,
                                   comment_sort: dict | None = None,
                                   comment_limit: int | None = 0,
                                   element_sort: dict | None = None,
                                   element_limit: int | None = 0) -> Self | None:
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
                comments = await ChangesetComment.find_many_by_changeset_id(changeset_id,
                                                                            sort=comment_sort,
                                                                            limit=comment_limit)
                comments_count = len(comments)
            else:
                comments_count = await ChangesetComment.count_by_changeset_id(changeset_id)

        async def assign_elements() -> None:
            if element_limit != 0:
                nonlocal elements
                elements = await Element.find_many_by_changeset_id(changeset_id,
                                                                   sort=element_sort,
                                                                   limit=element_limit)

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

    def update_size_without_save(self, n: int) -> bool:
        new_size = self.size + n
        max_size = Auth.user().changeset_max_size
        if new_size == max_size:
            # automatically close the changeset if it reaches the max size
            if not self.closed_at:
                self.closed_at = utcnow()
            self.size = new_size
            return True
        elif new_size < max_size:
            self.size = new_size
            return True
        else:
            return False

    def update_boundary_without_save(self, geometry: BaseGeometry) -> None:
        self.boundary = box(*(self.boundary.union(geometry).bounds if self.boundary else geometry.bounds))
