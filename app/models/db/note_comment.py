from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import NotRequired, TypedDict

from app.lib.render.rich_text import resolve_rich_text
from app.lib.text.note_hashtags import append_note_hashtags
from app.models.db.note import Note
from app.models.db.user import UserDisplay
from app.models.proto.note_types import GetCommentsResponse_Comment_Event
from app.models.types import NoteCommentId, NoteId, UserId


class NoteComment(TypedDict):
    id: NoteCommentId
    user_id: UserId | None
    user_ip: IPv4Address | IPv6Address | None
    note_id: NoteId
    event: GetCommentsResponse_Comment_Event
    body: str  # TODO: validate size
    tags: dict[str, str] | None
    body_rich_hash: bytes | None
    created_at: datetime

    # runtime
    user: NotRequired[UserDisplay]
    body_rich: NotRequired[str]
    legacy_note: NotRequired[Note]


async def note_comments_resolve_rich_text(objs: list[NoteComment]):
    # Render each comment's immutable snapshot, never the note's current tags.
    # Keep the stored/returned body separate from its compatibility presentation.
    rendered: dict[NoteCommentId, NoteComment] = {
        obj['id']: {**obj, 'body': note_comment_text(obj)} for obj in objs
    }
    await resolve_rich_text(list(rendered.values()), 'note_comment', 'body', 'plain')
    for obj in objs:
        result = rendered[obj['id']]
        assert 'body_rich' in result
        obj['body_rich'] = result['body_rich']
        obj['body_rich_hash'] = result['body_rich_hash']


def note_comment_text(comment: NoteComment) -> str:
    return append_note_hashtags(comment['body'], comment.get('tags'))
