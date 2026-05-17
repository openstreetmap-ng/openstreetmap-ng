from typing import NamedTuple

import cython

from app.db import db_count, db_fetchall, db_fetchone, db_fetchrow, t_and, t_order
from app.exceptions.context import raise_for
from app.lib.auth.context import auth_user
from app.models.db.message import Message, MessageRecipient
from app.models.db.user import user_is_admin, user_is_moderator
from app.models.types import MessageId, UserId


class _MessageCountByUserResult(NamedTuple):
    total: int
    unread: int
    sent: int


class MessageQuery:
    @staticmethod
    async def get_by_id(message_id: MessageId) -> Message:
        """Get a message and its recipients by id."""
        user = auth_user(required=True)
        user_id = user['id']
        is_moderator = user_is_moderator(user)
        is_admin = user_is_admin(user)

        message = await db_fetchone(
            Message,
            t"""
                SELECT * FROM message
                WHERE id = {message_id} AND (
                    (from_user_id = {user_id} AND NOT from_user_hidden)
                    OR EXISTS (
                        SELECT 1 FROM message_recipient
                        WHERE message_id = id
                        AND user_id = {user_id}
                        AND NOT hidden
                    )
                    OR EXISTS (
                        SELECT 1 FROM report_comment
                        WHERE action = 'user_message'
                        AND action_id = {message_id}
                        AND (
                            (visible_to = 'moderator' AND {is_moderator})
                            OR (visible_to = 'administrator' AND {is_admin})
                        )
                    )
                )
            """,
        )
        if message is None:
            raise_for.message_not_found(message_id)

        await MessageQuery.resolve_recipients(user_id, [message])
        return message

    @staticmethod
    async def find_by_ids(ids: list[MessageId]) -> list[Message]:
        """Find messages by ids for report context."""
        return await db_fetchall(
            Message,
            t"""
                SELECT * FROM message
                WHERE id = ANY({ids})
            """,
        )

    @staticmethod
    async def find(
        *,
        inbox: bool,
        after: MessageId | None = None,
        before: MessageId | None = None,
        limit: int,
        resolve_recipients: bool = False,
        show: MessageId | None = None,
    ):
        """Get user messages."""
        user = auth_user(required=True)
        user_id = user['id']
        is_moderator = show is not None and user_is_moderator(user)
        is_admin = show is not None and user_is_admin(user)

        order_desc: cython.bint = (after is None) or (before is not None)

        if inbox:
            show_id = show or 0
            inbox_cond = t"""
                (EXISTS (
                    SELECT 1 FROM message_recipient
                    WHERE message_id = id
                    AND user_id = {user_id}
                    AND NOT hidden
                ) OR (id = {show_id} AND EXISTS (
                    SELECT 1 FROM report_comment
                    WHERE action = 'user_message'
                    AND action_id = {show_id}
                    AND (
                        (visible_to = 'moderator' AND {is_moderator})
                        OR (visible_to = 'administrator' AND {is_admin})
                    )
                )))
            """
        else:
            inbox_cond = t'from_user_id = {user_id} AND NOT from_user_hidden'

        where = t_and(
            inbox_cond,
            t'id > {after}' if after is not None else None,
            t'id < {before}' if before is not None else None,
        )
        order = t_order('desc' if order_desc else 'asc')

        query = t"""
            SELECT * FROM message
            WHERE {where:q}
            ORDER BY id {order:q}
            LIMIT {limit}
        """

        # Always return in consistent order regardless of the query
        if not order_desc:
            query = t"""
                SELECT * FROM ({query:q})
                ORDER BY id DESC
            """

        rows = await db_fetchall(Message, query)

        if resolve_recipients:
            await MessageQuery.resolve_recipients(user_id, rows)
        return rows

    @staticmethod
    async def resolve_recipients(current_user_id: UserId | None, items: list[Message]):
        """Resolve recipients for a list of messages."""
        if not items:
            return

        id_map: dict[MessageId, list[MessageRecipient]] = {}
        for item in items:
            item['recipients'] = recipients = []
            id_map[item['id']] = recipients
        ids = list(id_map)

        rows = await db_fetchall(
            MessageRecipient,
            t"""
                SELECT * FROM message_recipient
                WHERE message_id = ANY({ids})
            """,
        )
        for row in rows:
            id_map[row['message_id']].append(row)

        if current_user_id is None:
            return

        # Resolve user_recipient when the current user is known
        for item in items:
            user_recipient = next(
                (
                    r
                    for r in item['recipients']  # pyright: ignore[reportTypedDictNotRequiredAccess]
                    if r['user_id'] == current_user_id
                ),
                None,
            )
            if user_recipient is not None:
                item['user_recipient'] = user_recipient

    @staticmethod
    async def count_unread() -> int:
        """Count all unread received messages for the current user."""
        user_id = auth_user(required=True)['id']
        return await db_count(
            'message_recipient',
            where=t'user_id = {user_id} AND NOT hidden AND NOT read',
        )

    @staticmethod
    async def count_by_user(user_id: UserId):
        """Count received messages by user id."""
        row = await db_fetchrow(t"""
            SELECT
            (   SELECT COUNT(*) FROM message_recipient
                WHERE user_id = {user_id} AND NOT hidden),
            (   SELECT COUNT(*) FROM message_recipient
                WHERE user_id = {user_id} AND NOT hidden AND NOT read),
            (   SELECT COUNT(*) FROM message
                WHERE from_user_id = {user_id} AND NOT from_user_hidden)
        """)
        assert row is not None
        return _MessageCountByUserResult(*row)
