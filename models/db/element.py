from abc import ABC
from datetime import datetime
from itertools import chain
from typing import Self, Sequence

from geoalchemy2 import Geometry, WKBElement
from shapely.geometry import Polygon
from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from config import SRID
from lib.exceptions import Exceptions
from limits import MAP_QUERY_LEGACY_NODES_LIMIT
from models.db.base import _DEFAULT_FIND_LIMIT, Base
from models.db.changeset import Changeset
from models.db.created_at import CreatedAt
from models.db.user import User
from models.element_member import ElementMember
from models.element_type import ElementType
from models.typed_element_ref import TypedElementRef
from models.versioned_element_ref import VersionedElementRef
from utils import updating_cached_property, utcnow


class Element(Base.Sequential, CreatedAt, ABC):
    __tablename__ = 'element'
    # node_id_seq = Sequence('node_id_seq', metadata=Base.Sequential.metadata)
    # way_id_seq = Sequence('way_id_seq', metadata=Base.Sequential.metadata)
    # relation_id_seq = Sequence('relation_id_seq', metadata=Base.Sequential.metadata)

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(lazy='raise')
    changeset_id: Mapped[int] = mapped_column(ForeignKey(Changeset.id), nullable=False)
    changeset: Mapped[Changeset] = relationship(back_populates='elements', lazy='raise')
    type: Mapped[ElementType] = mapped_column(Enum(ElementType), nullable=False)
    typed_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tags: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    point: Mapped[WKBElement | None] = mapped_column(Geometry(geometry_type='POINT', srid=SRID), nullable=True)  # TODO: indexes, spatial_index
    members: Mapped[Sequence[ElementMember]] = mapped_column(JSONB, nullable=False)

    # BAD IDEA: sequences are not affected by transactions, just check latest id in table lock
    # https://docs.sqlalchemy.org/en/20/core/defaults.html#client-invoked-sql-expressions
    # typed_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=select(case({
    #     ElementType.node.value: node_id_seq.next_value(),
    #     ElementType.way.value: way_id_seq.next_value(),
    #     ElementType.relation.value: relation_id_seq.next_value(),
    # }, value=type)))

    # defaults
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    @validates('typed_id')
    def validate_typed_id(self, key: str, value: int):
        if value <= 0:
            raise RuntimeError('Element must have a positive id on creation')
        return value

    @validates('members')
    def validate_members(self, key: str, value: Sequence[ElementMember]):
        if any(member.typed_id <= 0 for member in value):
            raise RuntimeError('Element member must have a positive id on creation')
        return value

    # TODO: SQL
    @updating_cached_property(lambda self: self.typed_id)
    def typed_ref(self) -> TypedElementRef:
        return TypedElementRef(type=self.type, id=self.typed_id)

    @updating_cached_property(lambda self: self.typed_id)
    def versioned_ref(self) -> VersionedElementRef:
        return VersionedElementRef(type=self.type, id=self.typed_id, version=self.version)

    @updating_cached_property(lambda self: self.members)
    def references(self) -> frozenset[TypedElementRef]:
        return frozenset(member.ref for member in self.members)

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
