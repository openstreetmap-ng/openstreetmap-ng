from sqlalchemy import func, select

from app.db import db_autocommit
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.db.user import User


class MigrationService:
    @staticmethod
    async def fix_sequence_counters() -> None:
        """
        Fix the sequence counters.
        """
        async with db_autocommit() as session:
            stmt = select(func.setval('changeset_id_seq', func.max(Changeset.id)))
            await session.execute(stmt)

            stmt = select(func.setval('element_sequence_id_seq', func.max(Element.sequence_id)))
            await session.execute(stmt)

            stmt = select(func.setval('user_id_seq', func.max(User.id)))
            await session.execute(stmt)
