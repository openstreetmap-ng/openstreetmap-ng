from asyncio import TaskGroup

from feedgen.entry import FeedEntry
from feedgen.feed import FeedGenerator
from httpx import HTTPError
from shapely import get_coordinates

from app.config import API_URL, APP_URL
from app.lib.render_jinja import render_jinja
from app.lib.translation import t
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment
from app.queries.nominatim_query import NominatimQuery


class NoteRSS06Mixin:
    @staticmethod
    async def encode_notes(fg: FeedGenerator, notes: list[Note]) -> None:
        """Encode notes into a feed."""
        fg.load_extension('dc')
        fg.load_extension('geo')
        async with TaskGroup() as tg:
            for note in notes:
                fe = fg.add_entry(order='append')
                tg.create_task(_encode_note(fe, note))

    @staticmethod
    async def encode_note_comments(
        fg: FeedGenerator, comments: list[NoteComment]
    ) -> None:
        """Encode note comments into a feed."""
        fg.load_extension('dc')
        fg.load_extension('geo')
        async with TaskGroup() as tg:
            for comment in comments:
                fe = fg.add_entry(order='append')
                tg.create_task(_encode_note_comment(fe, comment))


async def _encode_note(fe: FeedEntry, note: Note) -> None:
    note_id = note['id']
    comments = note['comments']  # pyright: ignore [reportTypedDictNotRequiredAccess]
    api_permalink = f'{API_URL}/api/0.6/notes/{note_id}'
    web_permalink = f'{APP_URL}/note/{note_id}'

    fe.guid(api_permalink, permalink=True)
    fe.link(href=web_permalink)
    fe.content(
        render_jinja(
            'api06/note-feed-comments',
            {'comments': comments},
        ),
        type='CDATA',
    )
    fe.published(note['created_at'])
    fe.updated(note['updated_at'])

    x, y = get_coordinates(note['point'])[0].tolist()
    fe.geo.point(f'{y} {x}')

    user = comments[0].get('user')
    if user is not None:
        user_display_name = user['display_name']
        user_permalink = f'{APP_URL}/user-id/{user["id"]}'
        fe.author(name=user_display_name, uri=user_permalink)
        fe.dc.creator(user_display_name)

    place = f'{y:.5f}, {x:.5f}'
    try:
        # reverse geocode the note point
        result = await NominatimQuery.reverse(note['point'])
        if result is not None:
            place = result.display_name
    except HTTPError:
        pass

    if len(comments) == 1:
        fe.title(t('api.notes.rss.opened', place=place))
    else:
        for comment in comments[::-1]:
            comment_event = comment['event']
            if comment_event == 'hidden':
                continue  # skip hide events
            if comment_event == 'closed':
                fe.title(t('api.notes.rss.closed', place=place))
            else:
                fe.title(t('api.notes.rss.commented', place=place))
            break


async def _encode_note_comment(fe: FeedEntry, comment: NoteComment) -> None:
    legacy_note = comment['legacy_note']  # pyright: ignore [reportTypedDictNotRequiredAccess]
    permalink = f'{APP_URL}/note/{comment["note_id"]}#c{comment["id"]}'
    point = legacy_note['point']

    fe.guid(permalink, permalink=True)
    fe.link(href=permalink)
    fe.content(
        render_jinja(
            'api06/note-feed-entry',
            {'comment': comment, 'comments': legacy_note['comments']},  # pyright: ignore [reportTypedDictNotRequiredAccess]
        ),
        type='CDATA',
    )
    fe.published(comment['created_at'])

    x, y = get_coordinates(point)[0].tolist()
    fe.geo.point(f'{y} {x}')

    user = comment.get('user')
    if user is not None:
        user_display_name = user['display_name']
        user_permalink = f'{APP_URL}/user-id/{user["id"]}'
        fe.author(name=user_display_name, uri=user_permalink)
        fe.dc.creator(user_display_name)

    place = f'{y:.5f}, {x:.5f}'
    try:
        # reverse geocode the note point
        result = await NominatimQuery.reverse(point)
        if result is not None:
            place = result.display_name
    except HTTPError:
        pass

    comment_event = comment['event']
    if comment_event == 'opened':
        fe.title(t('api.notes.rss.opened', place=place))
    elif comment_event == 'closed':
        fe.title(t('api.notes.rss.closed', place=place))
    elif comment_event == 'reopened':
        fe.title(t('api.notes.rss.reopened', place=place))
    elif comment_event == 'commented':
        fe.title(t('api.notes.rss.commented', place=place))
    elif comment_event == 'hidden':
        fe.title(t('api.notes.rss.hidden', place=place))
    else:
        raise NotImplementedError(f'Unsupported note event {comment_event!r}')
