from sqlalchemy import ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base
from app.models.db.changeset import Changeset
from app.models.db.user import User


class ChangesetSubscription(Base.NoID):
    __tablename__ = 'changeset_subscription'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    changeset_id: Mapped[int] = mapped_column(ForeignKey(Changeset.id), nullable=False)

    __table_args__ = (PrimaryKeyConstraint(changeset_id, user_id),)
