from collections.abc import Sequence
from typing import Self

from sqlalchemy import ForeignKey, LargeBinary, UnicodeText, update
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from db import DB
from lib.cache import CACHE_HASH_SIZE
from lib.rich_text import RichText, rich_text_getter
from limits import CHANGESET_COMMENT_BODY_MAX_LENGTH
from models.db.base import _DEFAULT_FIND_LIMIT, Base
from models.db.changeset import Changeset
from models.db.created_at import CreatedAt
from models.db.user import User
from models.text_format import TextFormat


class ChangesetComment(Base.UUID, CreatedAt):
    __tablename__ = 'changeset_comment'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(back_populates='changeset_comments', lazy='raise')
    changeset_id: Mapped[int] = mapped_column(ForeignKey(Changeset.id), nullable=False)
    changeset: Mapped[Changeset] = relationship(back_populates='changeset_comments', lazy='raise')
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body_rich_hash: Mapped[bytes | None] = mapped_column(LargeBinary(CACHE_HASH_SIZE), nullable=True, default=None)

    @validates('body')
    def validate_body(self, _: str, value: str) -> str:
        if len(value) > CHANGESET_COMMENT_BODY_MAX_LENGTH:
            raise ValueError('Comment is too long')
        return value

    body_rich = rich_text_getter('body', TextFormat.plain)

    # TODO: SQL
    @classmethod
    async def find_many_by_changeset_id(
        cls, changeset_id: SequentialId, *, sort: dict | None = None, limit: int | None = _DEFAULT_FIND_LIMIT
    ) -> Sequence[Self]:
        return await cls.find_many({'changeset_id': changeset_id}, sort=sort, limit=limit)

    @classmethod
    async def count_by_changeset_id(cls, changeset_id: SequentialId) -> int:
        return await cls.count({'changeset_id': changeset_id})
