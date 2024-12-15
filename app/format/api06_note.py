from collections.abc import Iterable

import cython
import numpy as np
from lxml.etree import CDATA
from shapely import Point, lib

from app.config import API_URL, APP_URL
from app.lib.date_utils import format_sql_date, legacy_date
from app.lib.format_style_context import format_style
from app.lib.jinja_env import render
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment


class Note06Mixin:
    @staticmethod
    def encode_note(note: Note) -> dict:
        """
        >>> encode_note(Note(...))
        {'note': {'@lon': 0.1, '@lat': 51, 'id': 16659, ...}}
        """
        style = format_style()
        if style == 'json':
            return _encode_note(note, is_json=True, is_gpx=False)
        elif style == 'gpx':
            return {'wpt': _encode_note(note, is_json=False, is_gpx=True)}
        else:
            return {'note': _encode_note(note, is_json=False, is_gpx=False)}

    @staticmethod
    def encode_notes(notes: Iterable[Note]) -> dict:
        """
        >>> encode_notes([
        ...     Note(...),
        ...     Note(...),
        ... ])
        {'note': [{'@lon': 1, '@lat': 2, 'id': 1, ...}]}
        """
        style = format_style()
        if style == 'json':
            return {
                'type': 'FeatureCollection',
                'features': tuple(_encode_note(note, is_json=True, is_gpx=False) for note in notes),
            }
        elif style == 'gpx':
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
        'date': format_sql_date(legacy_date(comment.created_at)),
        **(
            {
                'uid': comment.user_id,
                'user': comment.user.display_name,  # pyright: ignore[reportOptionalMemberAccess]
                'user_url': f'{APP_URL}/user-id/{comment.user_id}',
            }
            if (comment.user_id is not None)
            else {}
        ),
        'action': comment.event.value,
        'text': comment.body,
        'html': comment.body_rich,
    }


@cython.cfunc
def _encode_note(note: Note, *, is_json: cython.char, is_gpx: cython.char) -> dict:
    """
    >>> _encode_note(Note(...))
    {'@lon': 0.1, '@lat': 51, 'id': 16659, ...}
    """
    created_at = legacy_date(note.created_at)
    closed_at = legacy_date(note.closed_at)
    if is_json:
        return {
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': _encode_point_json(note.point),
            },
            'properties': {
                'id': note.id,
                'url': f'{API_URL}/api/0.6/notes/{note.id}.json',
                **(
                    {
                        'reopen_url': f'{API_URL}/api/0.6/notes/{note.id}/reopen.json',
                    }
                    if (closed_at is not None)
                    else {
                        'comment_url': f'{API_URL}/api/0.6/notes/{note.id}/comment.json',
                        'close_url': f'{API_URL}/api/0.6/notes/{note.id}/close.json',
                    }
                ),
                'date_created': format_sql_date(created_at),
                **({'closed_at': format_sql_date(closed_at)} if (closed_at is not None) else {}),
                'status': note.status.value,
                'comments': tuple(_encode_note_comment(comment) for comment in note.comments),
            },
        }
    elif is_gpx:
        return {
            **_encode_point_xml(note.point),
            'time': created_at,
            'name': f'Note: {note.id}',
            'link': {'href': f'{APP_URL}/note/{note.id}'},
            'desc': CDATA(render('api06/note_feed_comments.jinja2', {'comments': note.comments})),
            'extensions': {
                'id': note.id,
                'url': f'{API_URL}/api/0.6/notes/{note.id}.gpx',
                **(
                    {
                        'reopen_url': f'{API_URL}/api/0.6/notes/{note.id}/reopen.gpx',
                    }
                    if (closed_at is not None)
                    else {
                        'comment_url': f'{API_URL}/api/0.6/notes/{note.id}/comment.gpx',
                        'close_url': f'{API_URL}/api/0.6/notes/{note.id}/close.gpx',
                    }
                ),
                'date_created': format_sql_date(created_at),
                **({'date_closed': format_sql_date(closed_at)} if (closed_at is not None) else {}),
                'status': note.status.value,
            },
        }
    else:
        return {
            **_encode_point_xml(note.point),
            'id': note.id,
            'url': f'{API_URL}/api/0.6/notes/{note.id}',
            **(
                {
                    'reopen_url': f'{API_URL}/api/0.6/notes/{note.id}/reopen',
                }
                if (closed_at is not None)
                else {
                    'comment_url': f'{API_URL}/api/0.6/notes/{note.id}/comment',
                    'close_url': f'{API_URL}/api/0.6/notes/{note.id}/close',
                }
            ),
            'date_created': format_sql_date(created_at),
            **({'date_closed': format_sql_date(closed_at)} if (closed_at is not None) else {}),
            'status': note.status.value,
            'comments': {'comment': tuple(_encode_note_comment(comment) for comment in note.comments)},
        }


@cython.cfunc
def _encode_point_json(point: Point) -> list[float]:
    """
    >>> _encode_point_json(Point(1, 2))
    [1, 2]
    """
    return lib.get_coordinates(np.asarray(point, dtype=np.object_), False, False)[0].tolist()


@cython.cfunc
def _encode_point_xml(point: Point) -> dict[str, float]:
    """
    >>> _encode_point_xml(Point(1, 2))
    {'@lon': 1, '@lat': 2}
    """
    x, y = lib.get_coordinates(np.asarray(point, dtype=np.object_), False, False)[0].tolist()
    return {'@lon': x, '@lat': y}
