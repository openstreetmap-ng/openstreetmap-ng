from sqlalchemy import ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.db.base import Base
from models.db.user import User


class Friendship(Base.NoID):
    __tablename__ = 'friendship'

    from_user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    to_user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)

    __table_args__ = (PrimaryKeyConstraint(from_user_id, to_user_id),)
