from sqlalchemy import (
    BigInteger,
    Enum,
    Index,
    PrimaryKeyConstraint,
    SmallInteger,
    Unicode,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base
from app.models.element import ElementId, ElementType


class ElementMember(Base.NoID):
    __tablename__ = 'element_member'

    sequence_id: Mapped[int] = mapped_column(BigInteger, init=False, nullable=False)
    order: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    type: Mapped[ElementType] = mapped_column(Enum('node', 'way', 'relation', name='element_type'), nullable=False)
    id: Mapped[ElementId] = mapped_column(BigInteger, nullable=False)
    role: Mapped[str] = mapped_column(Unicode(255), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(sequence_id, order, name='element_member_pkey'),
        Index('element_member_idx', type, id, sequence_id),
    )
