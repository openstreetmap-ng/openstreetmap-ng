from collections.abc import Sequence

import cython
import lxml.etree as ET
from shapely import Point, get_coordinates

from app.config import API_URL
from app.lib.date_utils import format_sql_date
from app.lib.format_style_context import format_style
from app.lib.translation import render
from app.lib.xmltodict import xattr
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment
from app.models.format_style import FormatStyle


class Note06Mixin:
    @staticmethod
    def encode_note(note: Note) -> dict:
        """
        >>> encode_note(Note(...))
        {'note': {'@lon': 0.1, '@lat': 51, 'id': 16659, ...}}
        """

        style = format_style()

        if style == FormatStyle.json:
            return _encode_note(note, is_json=True, is_gpx=False)
        elif style == FormatStyle.gpx:
            return {'wpt': _encode_note(note, is_json=False, is_gpx=True)}
        else:
            return {'note': _encode_note(note, is_json=False, is_gpx=False)}

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
            return {
                'type': 'FeatureCollection',
                'features': tuple(_encode_note(note, is_json=True, is_gpx=False) for note in notes),
            }
        elif style == FormatStyle.gpx:
            return {'wpt': tuple(_encode_note(note, is_json=False, is_gpx=True) for note in notes)}
        else:
            return {'note': tuple(_encode_note(note, is_json=False, is_gpx=False) for note in notes)}


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


@cython.cfunc
def _encode_note(note: Note, *, is_json: cython.char, is_gpx: cython.char) -> dict:
    """
    >>> _encode_note(Note(...))
    {'@lon': 0.1, '@lat': 51, 'id': 16659, ...}
    """

    if is_json:
        return {
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': get_coordinates(note.point)[0].tolist(),
            },
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
                **({'closed_at': format_sql_date(note.closed_at)} if (note.closed_at is not None) else {}),
                'status': note.status.value,
                'comments': tuple(_encode_note_comment(comment) for comment in note.comments),
            },
        }
    elif is_gpx:
        return {
            **_encode_point(note.point),
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
                **({'date_closed': format_sql_date(note.closed_at)} if (note.closed_at is not None) else {}),
                'status': note.status.value,
            },
        }
    else:
        return {
            **_encode_point(note.point),
            'id': note.id,
            'url': f'{API_URL}/api/0.6/notes/{note.id}',
            **(
                {
                    'reopen_url': f'{API_URL}/api/0.6/notes/{note.id}/reopen',
                }
                if note.closed_at is not None
                else {
                    'comment_url': f'{API_URL}/api/0.6/notes/{note.id}/comment',
                    'close_url': f'{API_URL}/api/0.6/notes/{note.id}/close',
                }
            ),
            'date_created': format_sql_date(note.created_at),
            **({'date_closed': format_sql_date(note.closed_at)} if (note.closed_at is not None) else {}),
            'status': note.status.value,
            'comments': {'comment': tuple(_encode_note_comment(comment) for comment in note.comments)},
        }


@cython.cfunc
def _encode_point(point: Point) -> dict:
    """
    >>> _encode_point(Point(1, 2))
    {'@lon': 1, '@lat': 2}
    """

    xattr_ = xattr  # read property once for performance
    x, y = get_coordinates(point)[0].tolist()

    return {
        xattr_('lon'): x,
        xattr_('lat'): y,
    }
