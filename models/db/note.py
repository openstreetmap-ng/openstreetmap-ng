from datetime import datetime, timedelta

from shapely import Point
from sqlalchemy import ColumnElement, DateTime, null, true
from sqlalchemy.ext.hybrid import hybrid_method
from sqlalchemy.orm import Mapped, mapped_column, relationship

from limits import NOTE_FRESHLY_CLOSED_TIMEOUT
from models.db.base import Base
from models.db.created_at import CreatedAt
from models.db.updated_at import UpdatedAt
from models.db.user import User
from models.geometry_type import PointType
from utils import utcnow


# TODO: ensure updated at on members
class Note(Base.Sequential, CreatedAt, UpdatedAt):
    __tablename__ = 'note'

    point: Mapped[Point] = mapped_column(PointType, nullable=False)

    # defaults
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    # relationships (nested imports to avoid circular imports)
    from note_comment import NoteComment

    note_comments: Mapped[list[NoteComment]] = relationship(
        back_populates='note',
        order_by='asc(NoteComment.created_at)',
        lazy='raise',
    )

    @property
    def freshly_closed_duration(self) -> timedelta | None:
        if self.closed_at is None:
            return None

        return self.closed_at + NOTE_FRESHLY_CLOSED_TIMEOUT - utcnow()

    @hybrid_method
    def visible_to(self, user: User | None) -> bool:
        if user and user.is_moderator:
            return True

        return self.hidden_at is None

    @visible_to.expression
    @classmethod
    def visible_to(cls, user: User | None) -> ColumnElement[bool]:
        if user and user.is_moderator:
            return true()

        return cls.hidden_at == null()
