from sqlalchemy import ForeignKey, LargeBinary, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lib.cache import CACHE_HASH_SIZE
from lib.rich_text import rich_text_getter
from models.db.base import Base
from models.db.changeset import Changeset
from models.db.created_at import CreatedAt
from models.db.user import User
from models.text_format import TextFormat


class ChangesetComment(Base.Sequential, CreatedAt):
    __tablename__ = 'changeset_comment'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(back_populates='changeset_comments', lazy='raise')
    changeset_id: Mapped[int] = mapped_column(ForeignKey(Changeset.id), nullable=False)
    changeset: Mapped[Changeset] = relationship(back_populates='changeset_comments', lazy='raise')
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body_rich_hash: Mapped[bytes | None] = mapped_column(LargeBinary(CACHE_HASH_SIZE), nullable=True, default=None)
    body_rich = rich_text_getter('body', TextFormat.plain)
