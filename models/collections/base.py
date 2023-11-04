import re
from typing import Annotated, Any, Self, Sequence

from bson import ObjectId
from motor.core import AgnosticClientSession, AgnosticCollection
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import DeleteOne, InsertOne, UpdateOne
from pymongo.results import BulkWriteResult

from db import MONGO_DB
from utils import unicode_normalize

_BAD_XML_RE = re.compile(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F\uFFFE\uFFFF]')  # XML 1.0
_DEFAULT_FIND_LIMIT = 100


class Base(BaseModel):
    # use_enum_values=True is unpredictable
    # see https://github.com/pydantic/pydantic/issues/6565
    model_config = ConfigDict(arbitrary_types_allowed=True, validate_default=True)

    id: Annotated[ObjectId | None, Field(alias='_id', frozen=True, default_factory=ObjectId)]

    _collection_name_: Annotated[str | None, Field(exclude=True, frozen=True)] = None
    '''
    The collection name override.

    By default, the collection name is `__class__.__name__`.
    '''

    @field_validator('*')
    @classmethod
    def str_validator(cls, v: Any) -> Any:
        if isinstance(v, str) and v:
            if _BAD_XML_RE.search(v):
                raise ValueError(f'Invalid XML 1.0 characters {v!r}')
            return unicode_normalize(v)
        return v

    @classmethod
    def _collection_name(cls) -> str:
        return cls._collection_name_.get_default() or cls.__name__

    @classmethod
    def _collection(cls) -> AgnosticCollection:
        return MONGO_DB[cls._collection_name()]

    def model_dump(self) -> dict:
        if not self.id:
            raise ValueError(f'{self.__class__.__qualname__} must have an id to be dumped')
        self.model_validate()
        data = super().model_dump(by_alias=True)
        return data

    def create_batch(self) -> InsertOne:
        data = self.model_dump()
        return InsertOne(data)

    async def create(self, *, session: AgnosticClientSession | None = None) -> BulkWriteResult:
        batch = (self.create_batch(),)
        return await self._collection().bulk_write(batch, ordered=False, session=session)

    def update_batch(self, condition: dict | None = None) -> UpdateOne:
        # safety check
        if self.id is None:
            raise ValueError('Cannot update a document without an id')

        if condition is None:
            condition = {}

        # TODO: check errors?
        data = self.model_dump()
        return UpdateOne({'_id': self.id, **condition}, {'$set': data})

    async def update(self, condition: dict | None = None, *, session: AgnosticClientSession | None = None) -> BulkWriteResult:
        batch = (self.update_batch(condition),)
        return await self._collection().bulk_write(batch, ordered=False, session=session)

    def delete_batch(self) -> DeleteOne:
        # safety check
        if self.id is None:
            raise ValueError('Cannot delete a document without an id')

        # TODO: check errors?
        return DeleteOne({'_id': self.id})

    async def delete(self, *, session: AgnosticClientSession | None = None) -> BulkWriteResult:
        batch = (self.delete_batch(),)
        return await self._collection().bulk_write(batch, ordered=False, session=session)

    @classmethod
    async def delete_by(cls, query: dict, *, session: AgnosticClientSession | None = None) -> BulkWriteResult:
        return await cls._collection().delete_many(query, session=session)

    @classmethod
    async def delete_by_id(cls, id_: Any, *, session: AgnosticClientSession | None = None) -> BulkWriteResult:
        return await cls.delete_by({'_id': id_}, session=session)

    @classmethod
    async def count(cls, query: dict) -> int:
        return await cls._collection().count_documents(query)

    @classmethod
    async def find_and_update(cls, query: dict, update: dict, *, sort: dict | None = None, return_after: bool = False, session: AgnosticClientSession | None = None) -> Self | None:
        doc = await cls._collection().find_one_and_update(query, update, sort=sort, return_document=return_after, session=session)
        if not doc:
            return None
        return cls.model_validate(doc)

    @classmethod
    async def find_many(cls, query: dict, *, sort: dict | None = None, limit: int | None = _DEFAULT_FIND_LIMIT) -> Sequence[Self]:
        cursor = cls._collection().find(query)
        if sort:
            cursor = cursor.sort(sort)
        if limit:
            cursor = cursor.limit(limit)
        result = []
        async for doc in cursor:
            result.append(cls.model_validate(doc))
        return result

    @classmethod
    async def find_one(cls, query: dict, *, sort: dict | None = None) -> Self | None:
        docs = await cls.find_many(query, sort=sort, limit=1)
        if not docs:
            return None
        return docs[0]

    @classmethod
    async def find_one_by_id(cls, id_: Any) -> Self | None:
        return await cls.find_one({'_id': id_})

    @classmethod
    async def get_many(cls, query: dict, *, sort: dict | None = None, limit: int | None = _DEFAULT_FIND_LIMIT) -> Sequence[Self]:
        '''
        Like `find_many`, but raises `ValueError` if no document matches.
        '''

        docs = await cls.find_many(query, sort=sort, limit=limit)
        if not docs:
            raise ValueError(f'No document matches for {query!r}')
        return docs

    @classmethod
    async def get_one(cls, query: dict, *, sort: dict | None = None) -> Self:
        docs = await cls.get_many(query, sort=sort, limit=1)
        if not docs:
            raise ValueError(f'No document matches for {query!r}')
        return docs[0]

    @classmethod
    async def get_one_by_id(cls, id_: Any) -> Self:
        return await cls.get_one({'_id': id_})
