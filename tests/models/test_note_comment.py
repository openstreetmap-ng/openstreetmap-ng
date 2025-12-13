from app.lib.auth_context import auth_context
from app.models.db.note_comment import note_comments_resolve_rich_text
from app.models.types import DisplayName
from app.queries.note_comment_query import NoteCommentQuery
from app.queries.user_query import UserQuery
from app.services.note_service import NoteService


async def test_note_comments_resolve_rich_text():
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    with auth_context(user, frozenset(('web_user',))):
        note_id = await NoteService.create(
            0, 0, test_note_comments_resolve_rich_text.__qualname__
        )
        comments = await NoteCommentQuery.find_comments_page(
            note_id, page=1, num_items=1, skip_header=False
        )
        header = next(iter(comments), None)
        assert header is not None
        assert header['event'] == 'opened'
        assert header['body_rich_hash'] is None
        await note_comments_resolve_rich_text([header])
        comments = await NoteCommentQuery.find_comments_page(
            note_id, page=1, num_items=1, skip_header=False
        )
        header = next(iter(comments), None)
        assert header is not None
        assert header['event'] == 'opened'
        assert header['body_rich_hash'] is not None
