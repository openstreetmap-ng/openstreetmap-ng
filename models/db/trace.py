from datetime import datetime
from typing import Annotated, Self, Sequence

import anyio
from pydantic import Field, PositiveInt

from db.transaction import Transaction, retry_transaction
from lib.tracks import Tracks
from models.db.base_sequential import BaseSequential, SequentialId
from models.db.trace_point import TracePoint
from models.db.user import User
from models.file_name import FileName
from models.geometry import PointGeometry
from models.scope import ExtendedScope
from models.str import NonEmptyStr, Str255
from models.trace_visibility import TraceVisibility
from utils import utcnow
from validators.url import URLSafeValidator


class Trace(BaseSequential):
    user_id: Annotated[SequentialId, Field(frozen=True)]
    name: FileName
    description: Str255
    size: Annotated[PositiveInt, Field(frozen=True)]
    start_point: Annotated[PointGeometry, Field(frozen=True)]
    visibility: TraceVisibility

    # defaults
    created_at: Annotated[datetime, Field(frozen=True, default_factory=utcnow)]
    tags: tuple[Annotated[Str255, URLSafeValidator], ...] = ()
    file_id: NonEmptyStr | None = None
    image_id: NonEmptyStr | None = None
    icon_id: NonEmptyStr | None = None

    @property
    def tag_string(self) -> str:
        return ', '.join(self.tags)

    @tag_string.setter
    def tag_string(self, s: str) -> None:
        if ',' in s:
            tags = s.split(',')
        else:
            # do as before for backwards compatibility
            # BUG: this produces weird behavior: 'a b, c' -> ['a b', 'c']; 'a b' -> ['a', 'b']
            tags = s.split()

        tags = (t.strip() for t in tags)
        tags = tuple(filter(None, tags))
        self.tags = tags

    @property
    def linked_to_user_in_api(self) -> bool:
        return self.visibility == TraceVisibility.identifiable

    @property
    def linked_to_user_on_site(self) -> bool:
        return self.visibility in (TraceVisibility.identifiable, TraceVisibility.public)

    @property
    def timestamps_via_api(self) -> bool:
        return self.visibility in (TraceVisibility.identifiable, TraceVisibility.trackable)

    @classmethod
    async def find_many_by_user_id(cls, user_id: SequentialId) -> tuple[Self, ...]:
        return await cls.find_many({'user_id': user_id})

    def model_dump(self) -> dict:
        if not self.file_id or not self.image_id or not self.icon_id:
            raise ValueError(f'{self.__class__.__qualname__} must have file_id, image_id and icon_id set to be dumped')
        return super().model_dump()

    def visible_to(self, user: User | None, scopes: Sequence[ExtendedScope]) -> bool:
        return self.linked_to_user_on_site or (user and self.user_id == user.id and ExtendedScope.read_gpx in scopes)

    @retry_transaction()
    async def delete(self) -> None:
        async with (anyio.create_task_group() as tg, Transaction() as session):
            tg.start_soon(TracePoint.delete_by, {'trace_id': self.id}, session=session)
            tg.start_soon(super().delete, session=session)

        async with anyio.create_task_group() as tg:
            tg.start_soon(Tracks.storage.delete, self.file_id)
            tg.start_soon(Tracks.storage.delete, self.image_id)
            tg.start_soon(Tracks.storage.delete, self.icon_id)
