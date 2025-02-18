from sqlalchemy import func, null, select, update
from sqlalchemy.orm import aliased

from app.db import db
from app.models.db import *  # noqa: F403
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment
from app.models.db.user import User


class MigrationService:
    @staticmethod
    async def fix_sequence_counters() -> None:
        """Fix the sequence counters"""
        async with db(True, no_transaction=True) as session:
            await session.execute(select(func.setval('user_id_seq', func.max(User.id))))
            await session.execute(select(func.setval('changeset_id_seq', func.max(Changeset.id))))
            await session.execute(select(func.setval('element_sequence_id_seq', func.max(Element.sequence_id))))
            await session.execute(select(func.setval('note_id_seq', func.max(Note.id))))
            await session.execute(select(func.setval('note_comment_id_seq', func.max(NoteComment.id))))

    @staticmethod
    async def fix_next_sequence_id() -> None:
        """Fix the element's next_sequence_id field"""
        async with db(True, no_transaction=True) as session:
            other = aliased(Element)
            next_seq_subquery = (
                select(other.sequence_id)
                .where(
                    other.type == Element.type,
                    other.id == Element.id,
                    other.version > Element.version,
                )
                .order_by(other.version.asc())
                .limit(1)
                .scalar_subquery()
            )
            stmt = (
                update(Element)
                .where(
                    Element.next_sequence_id == null(),
                    next_seq_subquery != null(),
                )
                .values({Element.next_sequence_id: next_seq_subquery})
                .inline()
            )
            await session.execute(stmt)
