from datetime import datetime
from trace import Trace
from typing import Annotated, Self, Sequence

from pydantic import Field, NonNegativeInt
from pymongo import ASCENDING, DESCENDING

from db.cursor import Cursor
from geoutils import mapping_mongo
from models.collections.base import _DEFAULT_FIND_LIMIT, Base
from models.collections.base_sequential import SequentialId
from models.collections.trace import Trace
from models.geometry import PointGeometry, PolygonGeometry
from models.trace_visibility import TraceVisibility
from utils import utcnow


# TODO: optimize?
class TracePoint(Base):
    track_idx: Annotated[NonNegativeInt, Field(frozen=True)]
    captured_at: Annotated[datetime, Field(frozen=True)]  # TODO: ensure not in future too much
    point: Annotated[PointGeometry, Field(frozen=True)]
    elevation: Annotated[float | None, Field(frozen=True)]

    # defaults
    trace_id: SequentialId | None = None

    trace_: Annotated[Trace | None, Field(exclude=True)] = None

    def model_dump(self) -> dict:
        if not self.trace_id:
            raise ValueError(f'{self.__class__.__qualname__} must have a trace id to be dumped')
        return super().model_dump()

    # TODO: limit offset for safety
    @classmethod
    async def find_many_by_geometry_with_(
            cls,
            cursor: Cursor | None,
            geometry: PolygonGeometry,
            *,
            limit: int | None = _DEFAULT_FIND_LIMIT,
            legacy_skip: int | None = None) -> tuple[Sequence[Self], Cursor]:
        pipeline = [
            {'$match': {
                **({'_id': {'$lt': cursor.id}} if cursor else {}),
                'point': {'$geoIntersects': {'$geometry': mapping_mongo(geometry)}},
            }},
            {'$sort': {'_id': DESCENDING}},
            {'$skip': legacy_skip} if legacy_skip else {},
            {'$limit': limit} if limit is not None else {},

            {'$facet': {
                # output the smallest id element
                'last': [
                    {'$sort': {'_id': ASCENDING}},
                    {'$limit': 1},
                ],

                # output the query
                'query': [
                    # join with trace
                    {'$lookup': {
                        'from': Trace._collection_name(),
                        'localField': 'trace_id',
                        'foreignField': '_id',
                        'as': 'trace_'
                    }},
                    {'$unwind': '$trace_'},

                    # split processing by trace visibility
                    {'$facet': {
                        'ordered': [
                            {'$match': {
                                'trace_.visibility': {'$in': [
                                    TraceVisibility.identifiable.value,
                                    TraceVisibility.trackable.value,
                                ]}
                            }},
                            {'$sort': {
                                'trace_id': DESCENDING,
                                'track_idx': ASCENDING,
                                'captured_at': ASCENDING
                            }}
                        ],
                        'unordered': [
                            {'$match': {
                                'trace_.visibility': {'$in': [
                                    TraceVisibility.public.value,
                                    TraceVisibility.private.value,
                                ]}
                            }},
                            {'$sort': {
                                'point.coordinates': ASCENDING
                            }}
                        ]
                    }},

                    # union and unwind
                    {'$project': {
                        'result': {'$concatArrays': ['$ordered', '$unordered']}
                    }},
                    {'$unwind': '$result'},
                    {'$replaceRoot': {'newRoot': '$result'}}
                ]
            }},

            # union and unwind for async read
            {'$project': {
                'result': {'$concatArrays': ['$last', '$query']}
            }},
            {'$unwind': '$result'},
            {'$replaceRoot': {'newRoot': '$result'}}
        ]

        doc_cursor = cls._collection().aggregate(pipeline)

        last_point = None
        trace_map: dict[SequentialId, Trace] = {}
        result = []

        async for doc in doc_cursor:
            trace_d = doc.pop('trace_')
            point = cls.model_validate(doc)

            # use trace cache for performance and reduced memory usage
            if not (trace := trace_map.get(point.trace_id)):
                trace = Trace.model_validate(trace_d)
                trace_map[point.trace_id] = trace

            point.trace_ = trace

            # confused? notice $facet's "last" and "query"
            if not last_point:
                last_point = point
            else:
                result.append(point)

        return result, Cursor(last_point.id if last_point else None, None)
