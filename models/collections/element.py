from abc import ABC
from datetime import datetime
from itertools import chain
from typing import Annotated, Self, Sequence

from motor.core import AgnosticClientSession
from pydantic import Field, PositiveInt, model_validator
from pymongo import DESCENDING
from shapely.geometry import Polygon

from db.counter import get_next_sequence
from geoutils import mapping_mongo
from lib.exceptions import Exceptions
from limits import MAP_QUERY_LEGACY_NODES_LIMIT
from models.collections.base import _DEFAULT_FIND_LIMIT
from models.collections.base_sequential import BaseSequential, SequentialId
from models.element_member import ElementMember
from models.element_type import ElementType
from models.str import EmptyStr255
from models.typed_element_ref import TypedElementRef
from models.versioned_element_ref import VersionedElementRef
from utils import updating_cached_property, utcnow
from validators.eq import Ne


class Element(BaseSequential, ABC):
    user_id: SequentialId
    type: Annotated[ElementType, Field(frozen=True)]
    typed_id: Annotated[int, Ne(0)]
    changeset_id: Annotated[SequentialId, Field(frozen=True)]
    version: Annotated[PositiveInt, Field(frozen=True)]
    visible: Annotated[bool, Field(frozen=True)]
    tags: Annotated[dict[EmptyStr255, EmptyStr255], Field(frozen=True)]
    members: tuple[ElementMember, ...]

    # defaults
    created_at: datetime | None = None
    # TODO: superseded_at: datetime | None = None

    _collection_name_: Annotated[str, Field(exclude=True, frozen=True)] = 'Element'

    @updating_cached_property(lambda self: self.typed_id)
    def typed_ref(self) -> TypedElementRef:
        return TypedElementRef(type=self.type, id=self.typed_id)

    @updating_cached_property(lambda self: self.typed_id)
    def versioned_ref(self) -> VersionedElementRef:
        return VersionedElementRef(type=self.type, id=self.typed_id, version=self.version)

    @updating_cached_property(lambda self: self.members)
    def references(self) -> frozenset[TypedElementRef]:
        return frozenset(member.ref for member in self.members)

    @model_validator(mode='after')
    def validate_not_visible(self) -> Self:
        if not self.visible:
            if self.version == 1:
                raise ValueError(f'{self.__class__.__qualname__} cannot be hidden if version is 1')
            if self.tags:
                self.tags = {}  # TODO: test this
            if self.members:
                self.members = ()
        return self

    def model_dump(self) -> dict:
        if self.typed_id <= 0:
            raise ValueError(f'{self.__class__.__qualname__} must have a positive id to be dumped')
        if any(member.ref.id <= 0 for member in self.members):
            raise ValueError(f'{self.__class__.__qualname__} members must have a positive id to be dumped')
        if not self.created_at:
            raise ValueError(f'{self.__class__.__qualname__} must have a creation date set to be dumped')
        return super().model_dump()

    @classmethod
    async def get_next_typed_sequence(cls, n: int, session: AgnosticClientSession | None) -> Sequence[SequentialId]:
        return await get_next_sequence(f'{cls._collection_name()}_{cls.type.value}', n, session)

    @classmethod
    async def find_many_by_changeset_id(cls, changeset_id: SequentialId, *, sort: dict | None = None, limit: int | None = _DEFAULT_FIND_LIMIT) -> Sequence[Self]:
        return await cls.find_many({'changeset_id': changeset_id}, sort=sort, limit=limit)

    @classmethod
    async def find_many_by_typed_ref(cls, typed_ref: TypedElementRef, *, limit: int | None = _DEFAULT_FIND_LIMIT) -> Sequence[Self]:
        return await cls.find_many({
            'type': typed_ref.type.value,
            'typed_id': typed_ref.id
        }, sort={
            'version': DESCENDING
        }, limit=limit)

    # TODO: write tests for missing pipeline matches

    @classmethod
    async def find_one_by_typed_ref(cls, typed_ref: TypedElementRef) -> Self | None:
        docs = await cls.find_many_by_typed_ref(typed_ref, limit=1)
        if not docs:
            return None
        return docs[0]

    @classmethod
    async def find_one_by_versioned_ref(cls, versioned_ref: VersionedElementRef) -> Self | None:
        return await cls.find_one({
            'type': versioned_ref.type.value,
            'typed_id': versioned_ref.id,
            'version': versioned_ref.version
        })

    @classmethod
    async def find_latest(cls) -> Self | None:
        return await cls.find_one({}, sort={
            'id': DESCENDING
        })

    # TODO: sort in cursor vs pipeline
    @classmethod
    async def find_many_by_query(cls, geometry: Polygon, *, nodes_limit: int | None = _DEFAULT_FIND_LIMIT, legacy_nodes_limit: bool = False) -> Sequence[Self]:
        # TODO: point in time
        point_in_time = utcnow()

        if legacy_nodes_limit:
            if nodes_limit != MAP_QUERY_LEGACY_NODES_LIMIT:
                raise ValueError('limit must be MAP_QUERY_NODES_LEGACY_LIMIT when legacy_nodes_limit is enabled')
            nodes_limit += 1

        geometry_mapping = mapping_mongo(geometry)
        pipeline = [
            # find all the nodes that match all the filters
            {'$match': {
                'superseded_at': {'$or': [None, {'$gt': point_in_time}]},
                'created_at': {'$lt': point_in_time},
                'point': {'$geoIntersects': {'$geometry': geometry_mapping}},
            }},
            {'$sort': {'id', DESCENDING}},  # TODO: cursor
            {'$limit': nodes_limit} if nodes_limit is not None else {},

            {'$facet': {
                # output all the nodes
                'nodes': [],

                'parent': [
                    # find all the parent ways and relations
                    {'$lookup': {
                        'from': cls._collection_name(),
                        'let': {'typed_id': '$typed_id'},
                        'pipeline': [
                            {'$match': {'$expr': {'$and': [
                                {'$eq': ['$superseded_at', {'$or': [None, {'$gt': point_in_time}]}]},
                                {'$eq': ['$created_at', {'$lt': point_in_time}]},  # TODO: filter also by type?
                                {'$eq': ['$members.ref.type', ElementType.node.value]},
                                {'$eq': ['$members.ref.id', '$$typed_id']},
                            ]}}},
                        ],
                        'as': 'parent'
                    }},
                    {'$unwind': '$parent'},
                    {'$replaceRoot': {'newRoot': '$parent'}},

                    {'$facet': {
                        # output all the parent ways and relations
                        'ways_and_relations': [],

                        'way': [
                            {'$match': {'type': ElementType.way.value}},
                            {'$facet': {
                                # output all the way nodes
                                'nodes': [
                                    {'$unwind': '$members'},
                                    {'$match': {'members.ref.type': ElementType.node.value}},
                                    {'$replaceRoot': {'newRoot': '$members'}},
                                ],

                                # output all the parent relations
                                'parents': [
                                    {'$lookup': {
                                        'from': cls._collection_name(),
                                        'let': {'typed_id': '$typed_id'},
                                        'pipeline': [
                                            {'$match': {'$expr': {'$and': [
                                                {'$eq': ['$superseded_at', {'$or': [None, {'$gt': point_in_time}]}]},
                                                {'$eq': ['$created_at', {'$lt': point_in_time}]},
                                                {'$eq': ['$members.ref.type', ElementType.way.value]},
                                                {'$eq': ['$members.ref.id', '$$typed_id']},
                                            ]}}},
                                        ],
                                        'as': 'parent'
                                    }},
                                    {'$unwind': '$parent'},
                                    {'$replaceRoot': {'newRoot': '$parent'}},
                                ],
                            }}
                        ],
                    }}
                ],
            }}
        ]

        cursor = cls._collection().aggregate(pipeline)
        result_map = (await cursor.to_list(1))[0]

        nodes = result_map['nodes']
        parent_ways_and_relations = result_map['parent']['ways_and_relations']
        parent_way_nodes = result_map['parent']['way']['nodes']
        parent_way_relations = result_map['parent']['way']['parents']

        if legacy_nodes_limit and len(nodes) > MAP_QUERY_LEGACY_NODES_LIMIT:
            Exceptions.get().raise_for_map_query_nodes_limit_exceeded()

        result_ids = set()
        result = []
        for doc in chain(nodes, parent_ways_and_relations, parent_way_nodes, parent_way_relations):
            if doc['id'] not in result_ids:
                result_ids.add(doc['id'])
                result.append(cls.model_validate(doc))
        return result

    async def get_referenced_by(self, type: ElementType | None = None, *, after: SequentialId | None = None, sort: dict | None = None, limit: int | None = _DEFAULT_FIND_LIMIT) -> Sequence['Element']:
        # TODO: index
        # TODO: point in time
        point_in_time = utcnow()

        # TODO: construct for performance after development
        return await self.find_many({
            'superseded_at': {'$or': [None, {'$gt': point_in_time}]},
            'created_at': {'$lt': point_in_time},
            'members.ref.type': self.type.value,
            'members.ref.id': self.typed_id,
            **({'type': type.value} if type else {}),
            **({'_id': {'$gt': after}} if after else {})
        }, sort=sort, limit=limit)

    async def get_references(self, type: ElementType | None = None, *, recurse_ways: bool = False, sort: dict | None = None, limit: int | None = _DEFAULT_FIND_LIMIT) -> Sequence['Element']:
        # TODO: point in time
        point_in_time = utcnow()

        if type:
            members = tuple(member for member in self.members if member.ref.type == type)
        else:
            members = self.members

        if not members:
            # small optimization
            return ()

        if recurse_ways and self.members:
            recurse_way_typed_ids = tuple(
                member.ref.id
                for member in self.members
                if member.ref.type == ElementType.way)
            recurse_way_skip_node_typed_ids = tuple(
                member.ref.id
                for member in self.members
                if member.ref.type == ElementType.node)
        else:
            recurse_way_typed_ids = ()
            recurse_way_skip_node_typed_ids = ()

        pipeline = [
            {'$match': {
                'superseded_at': {'$or': [None, {'$gt': point_in_time}]},
                'created_at': {'$lt': point_in_time},
                '$or': [
                    {
                        'type': member.ref.type.value,
                        'typed_id': member.ref.id
                    } for member in members
                ]
            }},

            # optionally recurse ways
            {'$unionWith': {
                'coll': self._collection_name(),
                'pipeline': [
                    {'$match': {
                        'superseded_at': {'$or': [None, {'$gt': point_in_time}]},
                        'created_at': {'$lt': point_in_time},
                        'type': ElementType.way.value,
                        'typed_id': {'$in': recurse_way_typed_ids}
                    }},

                    # unwind the member nodes and skip the ones that are already in the result set
                    {'$unwind': '$members'},
                    {'$match': {'members.ref.id': {'$nin': recurse_way_skip_node_typed_ids}}},
                    {'$replaceRoot': {'newRoot': '$members'}}
                ]
            }} if recurse_way_typed_ids else {}
        ]

        cursor = self._collection().aggregate(pipeline)
        if sort:
            cursor = cursor.sort(sort)
        if limit:
            cursor = cursor.limit(limit)

        result = []
        async for doc in cursor:
            result.append(self.model_validate(doc))
        return result
