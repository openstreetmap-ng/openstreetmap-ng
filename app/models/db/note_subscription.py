from sqlalchemy import ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base
from app.models.db.note import Note
from app.models.db.user import User


class NoteSubscription(Base.NoID):
    __tablename__ = 'note_subscription'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    note_id: Mapped[int] = mapped_column(ForeignKey(Note.id), nullable=False)

    __table_args__ = (PrimaryKeyConstraint(note_id, user_id),)
