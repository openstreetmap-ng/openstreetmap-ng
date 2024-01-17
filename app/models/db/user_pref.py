from sqlalchemy import BigInteger, ForeignKey, PrimaryKeyConstraint, Unicode
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base
from app.models.db.user import User


class UserPref(Base.NoID):
    __tablename__ = 'user_pref'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    app_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    key: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    value: Mapped[str] = mapped_column(Unicode(255), nullable=False)

    __table_args__ = (PrimaryKeyConstraint(user_id, app_id, key),)
