from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Literal, NotRequired, TypedDict

from app.lib.rich_text import resolve_rich_text
from app.models.db.note import Note
from app.models.db.user import UserDisplay
from app.models.types import NoteCommentId, NoteId, UserId

NoteEvent = Literal['opened', 'closed', 'reopened', 'commented', 'hidden']


class NoteCommentInit(TypedDict):
    user_id: UserId | None
    user_ip: IPv4Address | IPv6Address | None
    note_id: NoteId
    event: NoteEvent
    body: str  # TODO: validate size


class NoteComment(NoteCommentInit):
    id: NoteCommentId
    body_rich_hash: bytes | None
    created_at: datetime

    # runtime
    user: NotRequired[UserDisplay]
    body_rich: NotRequired[str]
    legacy_note: NotRequired[Note]


async def note_comments_resolve_rich_text(objs: list[NoteComment]) -> None:
    await resolve_rich_text(objs, 'note_comment', 'body', 'plain')
