from typing import TYPE_CHECKING

from shapely import Point
from sqlalchemy import ForeignKey, LargeBinary, Unicode, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.lib.crypto import HASH_SIZE
from app.lib.rich_text import RichTextMixin
from app.limits import DIARY_BODY_MAX_LENGTH, LANGUAGE_CODE_MAX_LENGTH
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.updated_at_mixin import UpdatedAtMixin
from app.models.db.user import User
from app.models.geometry import PointType
from app.models.text_format import TextFormat

if TYPE_CHECKING:
    from app.models.db.diary_comment import DiaryComment


class Diary(Base.Sequential, CreatedAtMixin, UpdatedAtMixin, RichTextMixin):
    __tablename__ = 'diary'
    __rich_text_fields__ = (('body', TextFormat.markdown),)

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(lazy='raise', innerjoin=True)
    title: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body_rich_hash: Mapped[bytes | None] = mapped_column(
        LargeBinary(HASH_SIZE),
        init=False,
        nullable=True,
        server_default=None,
    )
    language: Mapped[str] = mapped_column(Unicode(LANGUAGE_CODE_MAX_LENGTH), nullable=False)
    point: Mapped[Point | None] = mapped_column(PointType, nullable=True)

    # runtime
    body_rich: str | None = None
    comments: list['DiaryComment'] | None = None

    @validates('body')
    def validate_body(self, _: str, value: str) -> str:
        if len(value) > DIARY_BODY_MAX_LENGTH:
            raise ValueError(f'Diary body is too long ({len(value)} > {DIARY_BODY_MAX_LENGTH})')
        return value
