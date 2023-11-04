from typing import Annotated, Any, Sequence

from motor.core import AgnosticClientSession
from pydantic import Field, PositiveInt
from pymongo import InsertOne
from pymongo.results import BulkWriteResult

from db.counter import get_next_sequence
from models.collections.base import Base

SequentialId = PositiveInt


class BaseSequential(Base):
    id: Annotated[SequentialId | None, Field(alias='_id')] = None

    async def get_next_sequence(self, n: int, session: AgnosticClientSession | None) -> Sequence[SequentialId]:
        return await get_next_sequence(self._collection_name(), n, session)

    def create_batch(self, id_: Any | None = None) -> InsertOne:
        if self.id is None:
            if id_ is None:
                raise ValueError('Cannot create a document without an id or a specified id')
            self.id = id_
        else:
            if id_ is not None:
                raise ValueError('Cannot create a document with an id and a specified id')

        data = self.model_dump()
        return InsertOne(data)

    async def create(self, session: AgnosticClientSession | None) -> BulkWriteResult:
        id_ = (await self.get_next_sequence(1, session))[0] if self.id is None else None  # assign id if not set
        batch = (self.create_batch(id_),)
        return await self._collection().bulk_write(batch, ordered=False, session=session)
