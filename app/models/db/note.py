from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from anyio import create_task_group
from shapely import Point
from sqlalchemy import ColumnElement, null, true
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.ext.hybrid import hybrid_method
from sqlalchemy.orm import Mapped, mapped_column

from app.config import APP_URL
from app.lib.date_utils import utcnow
from app.limits import NOTE_FRESHLY_CLOSED_TIMEOUT
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.updated_at_mixin import UpdatedAtMixin
from app.models.db.user import User
from app.models.geometry import PointType
from app.models.note_status import NoteStatus

if TYPE_CHECKING:
    from app.models.db.note_comment import NoteComment


# TODO: ensure updated at on members
# TODO: pruner
class Note(Base.Sequential, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = 'note'

    point: Mapped[Point] = mapped_column(PointType, nullable=False)

    # defaults
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(True), nullable=True, server_default=None)
    hidden_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(True), nullable=True, server_default=None)

    # runtime
    comments: list['NoteComment'] | None = None

    @property
    def freshly_closed_duration(self) -> timedelta | None:
        if self.closed_at is None:
            return None

        return self.closed_at + NOTE_FRESHLY_CLOSED_TIMEOUT - utcnow()

    @hybrid_method
    def visible_to(self, user: User | None) -> bool:
        if user is not None and user.is_moderator:
            return True

        return self.hidden_at is None

    @visible_to.expression
    @classmethod
    def visible_to(cls, user: User | None) -> ColumnElement[bool]:
        if user is not None and user.is_moderator:
            return true()

        return cls.hidden_at == null()

    @property
    def permalink(self) -> str:
        """
        Get the note's permalink.

        >>> note.permalink
        'https://www.openstreetmap.org/note/123456'
        """

        return f'{APP_URL}/note/{self.id}'

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

    async def resolve_comments_rich_text(self) -> None:
        """
        Resolve rich text for all comments.
        """

        async with create_task_group() as tg:
            for comment in self.comments:
                tg.start_soon(comment.resolve_rich_text)
