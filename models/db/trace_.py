from collections.abc import Sequence
from typing import Self

import anyio
from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import ARRAY, Enum, ForeignKey, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from config import SRID
from lib.tracks import Tracks
from limits import TRACE_TAG_MAX_LENGTH, TRACE_TAGS_LIMIT
from models.db.base import Base
from models.db.created_at import CreatedAt
from models.db.user import User
from models.scope import ExtendedScope
from models.trace_visibility import TraceVisibility


class Trace(Base.Sequential, CreatedAt):
    __tablename__ = 'trace'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(back_populates='traces', lazy='raise')
    name: Mapped[str] = mapped_column(Unicode, nullable=False)
    description: Mapped[str] = mapped_column(Unicode, nullable=False)
    visibility: Mapped[TraceVisibility] = mapped_column(Enum(TraceVisibility), nullable=False)

    size: Mapped[int] = mapped_column(int, nullable=False)
    start_point: Mapped[WKBElement] = mapped_column(Geometry(geometry_type='POINT', srid=SRID), nullable=False)
    file_id: Mapped[str] = mapped_column(Unicode, nullable=False)
    image_id: Mapped[str] = mapped_column(Unicode, nullable=False)
    icon_id: Mapped[str] = mapped_column(Unicode, nullable=False)

    # defaults
    tags: Mapped[Sequence[str]] = mapped_column(ARRAY(Unicode), nullable=False, default=())

    from trace_point import TracePoint

    trace_points: Mapped[Sequence[TracePoint]] = relationship(
        back_populates='trace',
        order_by='asc(TracePoint.captured_at)',
        lazy='raise',
    )

    @validates('tags')
    def validate_tags(cls, key: str, value: Sequence[str]):
        if len(value) > TRACE_TAGS_LIMIT:
            raise ValueError('Too many tags')
        return value

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

        tags = (t.strip()[:TRACE_TAG_MAX_LENGTH].strip() for t in tags)
        tags = (t for t in tags if t)
        self.tags = tuple(set(tags))

    @property
    def linked_to_user_in_api(self) -> bool:
        return self.visibility == TraceVisibility.identifiable

    @property
    def linked_to_user_on_site(self) -> bool:
        return self.visibility in (TraceVisibility.identifiable, TraceVisibility.public)

    @property
    def timestamps_via_api(self) -> bool:
        return self.visibility in (TraceVisibility.identifiable, TraceVisibility.trackable)

    # TODO: SQL
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
        async with anyio.create_task_group() as tg, Transaction() as session:
            tg.start_soon(TracePoint.delete_by, {'trace_id': self.id}, session=session)
            tg.start_soon(super().delete, session=session)

        async with anyio.create_task_group() as tg:
            tg.start_soon(Tracks.storage.delete, self.file_id)
            tg.start_soon(Tracks.storage.delete, self.image_id)
            tg.start_soon(Tracks.storage.delete, self.icon_id)
