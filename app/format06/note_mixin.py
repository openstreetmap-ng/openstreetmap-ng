from collections.abc import Sequence

import cython
import lxml.etree as ET
from shapely import Point

from app.config import API_URL
from app.format06.geometry_mixin import Geometry06Mixin
from app.lib.date_utils import format_sql_date
from app.lib.format_style_context import format_style
from app.lib.translation import render
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment
from app.models.format_style import FormatStyle


@cython.cfunc
def _mapping_point(p: Point) -> dict:
    """
    Convert a Shapely point to a GeoJSON-like dict.

    This method is more efficient than using `shapely.geometry.mapping`.

    >>> _mapping_point(Point(1, 2))
    {'type': 'Point', 'coordinates': (1, 2)}
    """

    return {
        'type': 'Point',
        'coordinates': (p.x, p.y),
    }


@cython.cfunc
def _encode_note_comment(comment: NoteComment) -> dict:
    """
    >>> _encode_note_comment(NoteComment(...))
    {'date': '2019-06-15 08:26:04 UTC', 'uid': 1234, 'user': 'userName', ...}
    """

    return {
        'date': format_sql_date(comment.created_at),
        **(
            {
                'uid': comment.user_id,
                'user': comment.user.display_name,
            }
            if comment.user_id is not None
            else {}
        ),
        'user_url': comment.user.permalink,
        'action': comment.event.value,
        'text': comment.body,
        'html': comment.body_rich.value,  # a disaster waiting to happen
    }


class Note06Mixin:
    @staticmethod
    def encode_note(note: Note) -> dict:
        """
        >>> encode_note(Note(...))
        {'note': {'@lon': 0.1, '@lat': 51, 'id': 16659, ...}}
        """

        style = format_style()

        if style == FormatStyle.json:
            return {
                'type': 'Feature',
                'geometry': _mapping_point(note.point),
                'properties': {
                    'id': note.id,
                    'url': f'{API_URL}/api/0.6/notes/{note.id}.json',
                    **(
                        {
                            'reopen_url': f'{API_URL}/api/0.6/notes/{note.id}/reopen.json',
                        }
                        if note.closed_at is not None
                        else {
                            'comment_url': f'{API_URL}/api/0.6/notes/{note.id}/comment.json',
                            'close_url': f'{API_URL}/api/0.6/notes/{note.id}/close.json',
                        }
                    ),
                    'date_created': format_sql_date(note.created_at),
                    **({'closed_at': format_sql_date(note.closed_at)} if note.closed_at is not None else {}),
                    'status': note.status.value,
                    'comments': tuple(_encode_note_comment(comment) for comment in note.comments),
                },
            }
        elif style == FormatStyle.gpx:
            return {
                'wpt': {
                    **Geometry06Mixin.encode_point(note.point),
                    'time': note.created_at,
                    'name': f'Note: {note.id}',
                    'link': {'href': note.permalink},
                    'desc': ET.CDATA(render('api/0.6/note_feed_comments.jinja2', comments=note.comments)),
                    'extensions': {
                        'id': note.id,
                        'url': f'{API_URL}/api/0.6/notes/{note.id}.gpx',
                        **(
                            {
                                'reopen_url': f'{API_URL}/api/0.6/notes/{note.id}/reopen.gpx',
                            }
                            if note.closed_at is not None
                            else {
                                'comment_url': f'{API_URL}/api/0.6/notes/{note.id}/comment.gpx',
                                'close_url': f'{API_URL}/api/0.6/notes/{note.id}/close.gpx',
                            }
                        ),
                        'date_created': format_sql_date(note.created_at),
                        **({'date_closed': format_sql_date(note.closed_at)} if note.closed_at is not None else {}),
                        'status': note.status.value,
                    },
                }
            }
        else:
            return {
                'note': {
                    **Geometry06Mixin.encode_point(note.point),
                    'id': note.id,
                    'url': f'{API_URL}/api/0.6/notes/{note.id}',
                    **(
                        {
                            'reopen_url': f'{API_URL}/api/0.6/notes/{note.id}/reopen',
                        }
                        if note.closed_at
                        else {
                            'comment_url': f'{API_URL}/api/0.6/notes/{note.id}/comment',
                            'close_url': f'{API_URL}/api/0.6/notes/{note.id}/close',
                        }
                    ),
                    'date_created': format_sql_date(note.created_at),
                    **({'date_closed': format_sql_date(note.closed_at)} if note.closed_at is not None else {}),
                    'status': note.status.value,
                    'comments': {'comment': tuple(_encode_note_comment(comment) for comment in note.comments)},
                }
            }

    @staticmethod
    def encode_notes(notes: Sequence[Note]) -> dict:
        """
        >>> encode_notes([
        ...     Note(...),
        ...     Note(...),
        ... ])
        {'note': [{'@lon': 1, '@lat': 2, 'id': 1, ...}]}
        """

        style = format_style()

        if style == FormatStyle.json:
            return {'type': 'FeatureCollection', 'features': tuple(Note06Mixin.encode_note(note) for note in notes)}
        elif style == FormatStyle.gpx:
            return {'wpt': tuple(Note06Mixin.encode_note(note)['wpt'] for note in notes)}
        else:
            return {'note': tuple(Note06Mixin.encode_note(note)['note'] for note in notes)}
