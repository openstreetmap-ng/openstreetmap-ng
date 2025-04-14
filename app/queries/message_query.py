from typing import NamedTuple

import cython
from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable

from app.db import db
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.models.db.message import Message
from app.models.types import MessageId, UserId


class _MessageCountByUserResult(NamedTuple):
    total: int
    unread: int
    sent: int


class MessageQuery:
    @staticmethod
    async def get_message_by_id(message_id: MessageId) -> Message:
        """Get a message by id."""
        user_id = auth_user(required=True)['id']

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM message
                WHERE id = %s AND (
                    (from_user_id = %s AND NOT from_user_hidden)
                    OR (to_user_id = %s AND NOT to_user_hidden)
                )
                """,
                (message_id, user_id, user_id),
            ) as r,
        ):
            message = await r.fetchone()
            if message is None:
                raise_for.message_not_found(message_id)
            return message  # type: ignore

    @staticmethod
    async def get_messages(
        *,
        inbox: bool,
        after: MessageId | None = None,
        before: MessageId | None = None,
        limit: int,
    ) -> list[Message]:
        """Get user messages."""
        user_id = auth_user(required=True)['id']

        order_desc: cython.bint = (after is None) or (before is not None)
        conditions: list[Composable] = []
        params: list[object] = []

        if inbox:
            conditions.append(SQL('to_user_id = %s AND NOT to_user_hidden'))
            params.append(user_id)
        else:
            conditions.append(SQL('from_user_id = %s AND NOT from_user_hidden'))
            params.append(user_id)

        if after is not None:
            conditions.append(SQL('id > %s'))
            params.append(after)

        if before is not None:
            conditions.append(SQL('id < %s'))
            params.append(before)

        query = SQL("""
            SELECT * FROM message
            WHERE {conditions}
            ORDER BY id {order}
            LIMIT %s
        """).format(
            conditions=SQL(' AND ').join(conditions),
            order=SQL('DESC' if order_desc else 'ASC'),
        )
        params.append(limit)

        # Always return in consistent order regardless of the query
        if not order_desc:
            query = SQL("""
                SELECT * FROM ({})
                ORDER BY id DESC
            """).format(query)

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def count_unread() -> int:
        """Count all unread received messages for the current user."""
        user_id = auth_user(required=True)['id']

        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT COUNT(*) FROM message
                WHERE to_user_id = %s
                AND NOT to_user_hidden
                AND NOT read
                """,
                (user_id,),
            ) as r,
        ):
            return (await r.fetchone())[0]  # type: ignore

    @staticmethod
    async def count_by_user_id(user_id: UserId) -> _MessageCountByUserResult:
        """Count received messages by user id."""
        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT COUNT(*) FROM message
                WHERE to_user_id = %s AND NOT to_user_hidden
                UNION ALL
                SELECT COUNT(*) FROM message
                WHERE to_user_id = %s AND NOT to_user_hidden AND NOT read
                UNION ALL
                SELECT COUNT(*) FROM message
                WHERE from_user_id = %s AND NOT from_user_hidden
                """,
                (user_id, user_id, user_id),
            ) as r,
        ):
            (total,), (unread,), (sent,) = await r.fetchall()
            return _MessageCountByUserResult(total, unread, sent)
