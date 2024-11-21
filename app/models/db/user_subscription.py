import enum

from sqlalchemy import BigInteger, Enum, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base
from app.models.db.user import User


class UserSubscriptionTarget(str, enum.Enum):
    changeset = 'changeset'
    diary = 'diary'
    note = 'note'
    user = 'user'


class UserSubscription(Base.NoID):
    __tablename__ = 'user_subscription'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    target: Mapped[UserSubscriptionTarget] = mapped_column(Enum(UserSubscriptionTarget), nullable=False)
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (PrimaryKeyConstraint(target, target_id, user_id),)
