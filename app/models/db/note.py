import enum
from datetime import datetime
from typing import TYPE_CHECKING

from shapely import Point
from sqlalchemy import ColumnElement, null, true
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.ext.hybrid import hybrid_method
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.updated_at_mixin import UpdatedAtMixin
from app.models.db.user import User
from app.models.geometry import PointType

if TYPE_CHECKING:
    from app.models.db.note_comment import NoteComment


class NoteStatus(str, enum.Enum):
    open = 'open'
    closed = 'closed'
    hidden = 'hidden'


# TODO: ensure updated at on members
# TODO: pruner
class Note(Base.Sequential, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = 'note'

    point: Mapped[Point] = mapped_column(PointType, nullable=False)

    # defaults
    closed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(True),
        init=False,
        nullable=True,
        server_default=None,
    )
    hidden_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(True),
        init=False,
        nullable=True,
        server_default=None,
    )

    # runtime
    comments: list['NoteComment'] | None = None

    @hybrid_method
    def visible_to(self, user: User | None) -> bool:  # pyright: ignore[reportRedeclaration]
        if (user is not None) and user.is_moderator:
            return True
        return self.hidden_at is None

    @visible_to.expression
    @classmethod
    def visible_to(cls, user: User | None) -> ColumnElement[bool]:
        if (user is not None) and user.is_moderator:
            return true()
        return cls.hidden_at == null()

    @property
    def status(self) -> NoteStatus:
        """
        Get the note's status.

        >>> note.status
        NoteStatus.open
        """
        if self.hidden_at:
            return NoteStatus.hidden
        elif self.closed_at:
            return NoteStatus.closed
        else:
            return NoteStatus.open
