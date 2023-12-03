from collections.abc import Sequence

import anyio
from anyio.abc import TaskStatus
from feedgen.feed import FeedGenerator

from config import API_URL
from lib.nominatim import Nominatim
from lib.translation import render, t
from models.db.note import Note
from models.db.note_comment import NoteComment
from models.note_event import NoteEvent


class Format06RSS:
    @staticmethod
    async def _encode_note(
        fg: FeedGenerator,
        note: Note,
        task_status: TaskStatus = anyio.TASK_STATUS_IGNORED,
    ) -> None:
        fe = fg.add_entry(order='append')
        fe.guid(f'{API_URL}/api/0.6/notes/{note.id}', permalink=True)
        fe.link(href=note.permalink)
        fe.content(render('api/0.6/note_comments_rss.jinja2', comments=note.comments), type='CDATA')
        fe.published(note.created_at)
        fe.updated(note.updated_at)
        fe.geo.point(f'{note.point.y} {note.point.x}')

        if user := note.comments[0].user:
            fe.author(name=user.display_name, uri=user.permalink)
            fe.dc.creator(user.display_name)

        # use task_status to preserve the order of the notes
        task_status.started()

        # reverse geocode the note point
        place = await Nominatim.reverse_name(note.point, 14)

        if len(note.comments) == 1:
            fe.title(t('api.notes.rss.opened', place=place))
        else:
            for comment in reversed(note.comments):
                # skip hide events
                if comment.event == NoteEvent.hidden:
                    continue

                if comment.event == NoteEvent.closed:
                    fe.title(t('api.notes.rss.closed', place=place))
                else:
                    fe.title(t('api.notes.rss.commented', place=place))

                break

    @staticmethod
    async def encode_notes(fg: FeedGenerator, notes: Sequence[Note]) -> None:
        """
        Encode notes into a feed.
        """

        fg.load_extension('dc')
        fg.load_extension('geo')

        async with anyio.create_task_group() as tg:
            for note in notes:
                await tg.start(Format06RSS._encode_note, fg, note)

    @staticmethod
    async def _encode_note_comment(
        fg: FeedGenerator,
        comment: NoteComment,
        task_status: TaskStatus = anyio.TASK_STATUS_IGNORED,
    ) -> None:
        point = comment.note.point

        fe = fg.add_entry(order='append')
        fe.guid(comment.legacy_permalink, permalink=True)
        fe.link(href=comment.legacy_permalink)
        fe.content(
            render(
                'api/0.6/note_feed_entry_rss.jinja2',
                comment=comment,
                comments=comment.note.comments,
            ),
            type='CDATA',
        )
        fe.published(comment.created_at)
        fe.geo.point(f'{point.y} {point.x}')

        if user := comment.user:
            fe.author(name=user.display_name, uri=user.permalink)
            fe.dc.creator(user.display_name)

        # use task_status to preserve the order of the notes
        task_status.started()

        # reverse geocode the note point
        place = await Nominatim.reverse_name(point, 14)

        if comment.event == NoteEvent.opened:
            fe.title(t('api.notes.rss.opened', place=place))
        elif comment.event == NoteEvent.closed:
            fe.title(t('api.notes.rss.closed', place=place))
        elif comment.event == NoteEvent.reopened:
            fe.title(t('api.notes.rss.reopened', place=place))
        elif comment.event == NoteEvent.commented:
            fe.title(t('api.notes.rss.commented', place=place))
        elif comment.event == NoteEvent.hidden:
            fe.title(t('api.notes.rss.hidden', place=place))
        else:
            raise NotImplementedError(f'Unsupported note event {comment.event!r}')

    @staticmethod
    async def encode_note_comments(fg: FeedGenerator, comments: Sequence[NoteComment]) -> None:
        """
        Encode note comments into a feed.
        """

        fg.load_extension('dc')
        fg.load_extension('geo')

        async with anyio.create_task_group() as tg:
            for comment in comments:
                await tg.start(Format06RSS._encode_note_comment, fg, comment)
