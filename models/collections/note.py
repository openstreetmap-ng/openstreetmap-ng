from datetime import datetime, timedelta
from typing import Annotated, Self, Sequence

from pydantic import Field
from pymongo import ASCENDING, DESCENDING
from shapely.geometry import Polygon

from db.cursor import Cursor
from db.transaction import Transaction, retry_transaction
from geoutils import mapping_mongo
from lib.auth import Auth
from limits import NOTE_FRESHLY_CLOSED_TIMEOUT
from models.collections.base import _DEFAULT_FIND_LIMIT
from models.collections.base_sequential import BaseSequential, SequentialId
from models.collections.note_comment import NoteComment
from models.collections.user import User
from models.geometry import PointGeometry
from utils import utcnow


# TODO: notes updated_at
class Note(BaseSequential):
    point: Annotated[PointGeometry, Field(frozen=True)]

    # defaults
    closed_at: datetime | None = None
    hidden_at: datetime | None = None  # TODO: auto cleanup

    comments_: Annotated[tuple[NoteComment, ...] | None, Field(exclude=True)] = None

    @property
    def freshly_closed_duration(self) -> timedelta | None:
        if self.closed_at is None:
            return None

        return self.closed_at + NOTE_FRESHLY_CLOSED_TIMEOUT - utcnow()

    @classmethod
    async def find_many_by_geometry_with_(
            cls,
            cursor: Cursor | None,
            geometry: Polygon,
            max_closed_for: timedelta | None = None,
            *,
            limit: int | None = _DEFAULT_FIND_LIMIT) -> tuple[Sequence[Self], Cursor]:
        # intentionally not using cursor.time as it may lead to confusing results (working on 2 collections)
        user = Auth.user()
        min_closed_at = utcnow() - max_closed_for if max_closed_for else None
        pipeline = [
            # filter notes
            {'$match': {
                **({'_id': {'$lt': cursor.id}} if cursor else {}),
                'point': {'$geoIntersects': {'$geometry': mapping_mongo(geometry)}},
                **({'closed_at': {'$gte': min_closed_at}} if min_closed_at else {}),
                **({'hidden_at': None} if not (user and user.is_moderator) else {})
            }},

            {'$sort': {'_id': DESCENDING}},
            {'$limit': limit} if limit is not None else {},

            # join comments
            {'$lookup': {
                'from': NoteComment._collection_name(),
                'localField': '_id',
                'foreignField': 'note_id',
                'pipeline': [
                    {'$sort': {'created_at': ASCENDING}},
                ],
                'as': 'comments_',
            }},
        ]

        doc_cursor = await cls._collection().aggregate(pipeline)
        result = []
        async for doc in doc_cursor:
            result.append(cls.model_validate(doc))
        return result, Cursor(result[-1].id if result else None, None)

    @classmethod
    async def find_many_by_search_with_(
            cls,
            *,
            geometry: Polygon | None = None,
            max_closed_for: timedelta | None = None,
            q: str | None = None,
            user_id: SequentialId | None = None,
            from_: datetime | None = None,
            to: datetime | None = None,
            sort: dict | None = None,
            limit: int | None = _DEFAULT_FIND_LIMIT) -> Sequence[Self]:
        if len(sort) != 1:
            raise ValueError('Sort must specify exactly one field')

        user = Auth.user()
        sort_key = next(iter(sort))
        min_closed_at = utcnow() - max_closed_for if max_closed_for else None

        if q:
            # force phrase match to get decent performance
            # wrap in double quotes and escape
            q = q.replace('\\', '\\\\').replace('"', '\\"')
            q = f'"{q}"'

        # if matching by query or user, aggregate on NoteComment collection
        if q or user_id:
            pipeline_target = NoteComment
            pre_pipeline = [
                # filter comments
                {'$match': {
                    **({'$text': {'$search': q}} if q else {}),
                    **({'user_id': user_id} if user_id else {}),
                }},

                # join notes and discard comment data
                {'$lookup': {
                    'from': cls._collection_name(),
                    'localField': 'note_id',
                    'foreignField': '_id',
                    'as': 'note_',
                }},
                {'$unwind': '$note_'},
                {'$replaceRoot': {'newRoot': '$note_'}},

                # deduplicate
                {'$group': {'_id': '$_id', 'first': {'$first': '$$ROOT'}}},
                {'$replaceRoot': {'newRoot': '$first'}},
            ]
        # otherwise, aggregate on Note collection directly
        else:
            pipeline_target = cls
            pre_pipeline = []

        pipeline = pre_pipeline + [
            # filter notes
            {'$match': {
                **({'point': {'$geoIntersects': {'$geometry': mapping_mongo(geometry)}}} if geometry else {}),
                **({'closed_at': {'$gte': min_closed_at}} if min_closed_at else {}),
                **({'hidden_at': None} if not (user and user.is_moderator) else {}),
                sort_key: {
                    **({'$gte': from_} if from_ else {}),
                    **({'$lt': to} if to else {}),
                }
            }},

            {'$sort': sort},
            {'$limit': limit} if limit is not None else {},

            # join comments
            {'$lookup': {
                'from': NoteComment._collection_name(),
                'localField': '_id',
                'foreignField': 'note_id',
                'pipeline': [
                    {'$sort': {'created_at': ASCENDING}},
                ],
                'as': 'comments_',
            }},
        ]

        doc_cursor = await pipeline_target._collection().aggregate(pipeline)
        result = []
        async for doc in doc_cursor:
            result.append(cls.model_validate(doc))
        return result

    def visible_to(self, user: User | None) -> bool:
        return not self.hidden_at or (user and user.is_moderator)

    @retry_transaction()
    async def create_with_comment(self, comment: NoteComment) -> None:
        self.id = None

        async with Transaction() as session:
            await self.create(session)
            comment.note_id = self.id
            await comment.create(session)

    # def close(self):
    #     # safety check
    #     if self.status == NoteStatus.closed:
    #         raise ValueError('Cannot close an already closed note')

    #     self.status = NoteStatus.closed
    #     self.closed_at = time()

    # def reopen(self):
    #     # safety check
    #     if self.status == NoteStatus.open:
    #         raise ValueError('Cannot reopen an already open note')

    #     self.status = NoteStatus.open
    #     self.closed_at = None
