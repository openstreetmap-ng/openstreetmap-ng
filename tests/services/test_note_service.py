from app.config import NOTE_CREATED_BY_HASHTAG
from app.lib.auth.context import auth_context
from app.models.types import DisplayName
from app.queries.note_query import NoteCommentQuery
from app.queries.user_query import UserQuery
from app.services.note_service import NoteService


async def test_note_create_appends_app_hashtag():
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    with auth_context(user, frozenset(('web_user',))):
        text = test_note_create_appends_app_hashtag.__qualname__
        note_id = await NoteService.create(0, 0, text, append_app_hashtag=True)
        header = await NoteCommentQuery.find_header(note_id)
        assert header is not None
        assert header['event'] == 'opened'
        assert header['body'] == f'{text}\n{NOTE_CREATED_BY_HASHTAG}'


async def test_note_create_appends_app_hashtag_empty_text():
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    with auth_context(user, frozenset(('web_user',))):
        note_id = await NoteService.create(0, 0, '', append_app_hashtag=True)
        header = await NoteCommentQuery.find_header(note_id)
        assert header is not None
        assert header['body'] == NOTE_CREATED_BY_HASHTAG


async def test_note_create_appends_app_hashtag_idempotent():
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    with auth_context(user, frozenset(('web_user',))):
        text = f'already tagged {NOTE_CREATED_BY_HASHTAG}'
        note_id = await NoteService.create(0, 0, text, append_app_hashtag=True)
        header = await NoteCommentQuery.find_header(note_id)
        assert header is not None
        assert header['body'] == text


async def test_note_create_without_flag_keeps_text_verbatim():
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    with auth_context(user, frozenset(('web_user',))):
        text = test_note_create_without_flag_keeps_text_verbatim.__qualname__
        note_id = await NoteService.create(0, 0, text)
        header = await NoteCommentQuery.find_header(note_id)
        assert header is not None
        assert header['body'] == text
