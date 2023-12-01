from sqlalchemy import ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.db.base import Base
from models.db.diary import Diary
from models.db.user import User


class DiarySubscription(Base.NoID):
    __tablename__ = 'diary_subscription'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    diary_id: Mapped[int] = mapped_column(ForeignKey(Diary.id), nullable=False)

    __table_args__ = (PrimaryKeyConstraint(diary_id, user_id),)
