from typing import TYPE_CHECKING

from shapely import Point
from sqlalchemy import ForeignKey, Index, LargeBinary, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.lib.crypto import HASH_SIZE
from app.lib.rich_text import RichTextMixin, TextFormat
from app.limits import DIARY_BODY_MAX_LENGTH, DIARY_TITLE_MAX_LENGTH, LOCALE_CODE_MAX_LENGTH
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.updated_at_mixin import UpdatedAtMixin
from app.models.db.user import User
from app.models.geometry import PointType
from app.models.types import LocaleCode

if TYPE_CHECKING:
    from app.models.db.diary_comment import DiaryComment


class Diary(Base.Sequential, CreatedAtMixin, UpdatedAtMixin, RichTextMixin):
    __tablename__ = 'diary'
    __rich_text_fields__ = (('body', TextFormat.markdown),)

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(lazy='raise', innerjoin=True)
    title: Mapped[str] = mapped_column(Unicode(DIARY_TITLE_MAX_LENGTH), nullable=False)
    body: Mapped[str] = mapped_column(Unicode(DIARY_BODY_MAX_LENGTH), nullable=False)
    body_rich_hash: Mapped[bytes | None] = mapped_column(
        LargeBinary(HASH_SIZE),
        init=False,
        nullable=True,
        server_default=None,
    )
    language: Mapped[LocaleCode] = mapped_column(Unicode(LOCALE_CODE_MAX_LENGTH), nullable=False)
    point: Mapped[Point | None] = mapped_column(PointType, nullable=True)

    # runtime
    body_rich: str | None = None
    comments: list['DiaryComment'] | None = None

    __table_args__ = (
        Index('diary_user_id_idx', user_id, 'id'),
        Index('diary_language_idx', language, 'id'),
    )

    @validates('body')
    def validate_body(self, _: str, value: str) -> str:
        if len(value) > DIARY_BODY_MAX_LENGTH:
            raise ValueError(f'Diary body is too long ({len(value)} > {DIARY_BODY_MAX_LENGTH})')
        return value
