from anyio import create_task_group
from shapely import Point
from sqlalchemy import ForeignKey, LargeBinary, Unicode, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.lib.crypto import HASH_SIZE
from app.lib.rich_text_mixin import RichTextMixin
from app.limits import DIARY_BODY_MAX_LENGTH, LANGUAGE_CODE_MAX_LENGTH
from app.models.cache_entry import CacheEntry
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.updated_at_mixin import UpdatedAtMixin
from app.models.db.user import User
from app.models.geometry_type import PointType
from app.models.text_format import TextFormat


class Diary(Base.Sequential, CreatedAtMixin, UpdatedAtMixin, RichTextMixin):
    __tablename__ = 'diary'
    __rich_text_fields__ = (('body', TextFormat.markdown),)

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(lazy='raise')
    title: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body_rich_hash: Mapped[bytes | None] = mapped_column(LargeBinary(HASH_SIZE), nullable=True, server_default=None)
    body_rich: CacheEntry | None = None
    language_code: Mapped[str] = mapped_column(Unicode(LANGUAGE_CODE_MAX_LENGTH), nullable=False)
    point: Mapped[Point | None] = mapped_column(PointType, nullable=True)

    @validates('body')
    def validate_body(self, _: str, value: str) -> str:
        if len(value) > DIARY_BODY_MAX_LENGTH:
            raise ValueError('Diary is too long')
        return value

    async def resolve_comments_rich_text(self) -> None:
        """
        Resolve rich text for all comments.
        """

        async with create_task_group() as tg:
            for comment in self.comments:
                tg.start_soon(comment.resolve_rich_text)
