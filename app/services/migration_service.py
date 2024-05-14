from sqlalchemy import func, select, text, update
from sqlalchemy.orm import aliased

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

    @staticmethod
    async def fix_changeset_table() -> None:
        """
        Fix the changeset table.
        """
        async with db_autocommit() as session:
            stmt = update(Changeset).values(
                {
                    Changeset.closed_at: select(func.max(Element.created_at))
                    .where(Element.changeset_id == Changeset.id)
                    .scalar_subquery(),
                    Changeset.size: select(func.count())
                    .select_from(text('1'))
                    .where(Element.changeset_id == Changeset.id)
                    .scalar_subquery(),
                }
            )
            await session.execute(stmt)

    @staticmethod
    async def fix_element_table() -> None:
        """
        Fix the element table.
        """
        async with db_autocommit() as session:
            E = aliased(Element)  # noqa: N806
            stmt = update(Element).values(
                {
                    Element.next_sequence_id: select(E.sequence_id)
                    .where(
                        E.type == Element.type,
                        E.id == Element.id,
                        E.version > Element.version,
                    )
                    .order_by(E.version.asc())
                    .limit(1)
                    .scalar_subquery()
                }
            )
            await session.execute(stmt)
