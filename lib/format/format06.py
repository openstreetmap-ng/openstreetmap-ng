import html
from abc import ABC
from collections import defaultdict
from datetime import datetime
from typing import Sequence

from shapely.geometry import Point, mapping

from config import BASE_URL, GENERATOR
from lib.auth import Auth
from lib.exceptions import Exceptions
from lib.format import Format
from lib.xmltodict import XAttr
from models.collections.base_sequential import SequentialId
from models.collections.changeset import Changeset
from models.collections.changeset_comment import ChangesetComment
from models.collections.element import Element
from models.collections.element_node import ElementNode
from models.collections.element_relation import ElementRelation
from models.collections.element_way import ElementWay
from models.collections.note import Note
from models.collections.note_comment import NoteComment
from models.collections.trace import Trace
from models.collections.trace_point import TracePoint
from models.collections.user import User
from models.element_member import ElementMember
from models.element_type import ElementType
from models.osmchange_action import OSMChangeAction
from models.trace_visibility import TraceVisibility
from models.typed_element_ref import TypedElementRef
from utils import format_sql_date


class Format06(ABC):
    @classmethod
    def encode_tags(cls, tags: dict) -> Sequence[dict] | dict:
        '''
        Encode a dict of tags to a sequence in 0.6 format.

        >>> cls.encode_tags({'a': '1', 'b': '2'})
        ({'@k': 'a', '@v': '1'}, {'@k': 'b', '@v': '2'})
        '''

        if Format.is_json():
            return tags
        else:
            return tuple(
                {'@k': k, '@v': v}
                for k, v in tags.items())

    @classmethod
    def decode_tags(cls, tags: Sequence[dict]) -> dict:
        '''
        Decode a sequence of tags from 0.6 format to a dict.

        >>> cls.decode_tags([
        ...     {'@k': 'a', '@v': '1'},
        ...     {'@k': 'b', '@v': '2'},
        ... ])
        {'a': '1', 'b': '2'}
        '''

        items = tuple((tag['@k'], tag['@v']) for tag in tags)
        result = dict(items)

        if len(items) != len(result):
            raise ValueError('Duplicate tags keys')

        return result

    @classmethod
    def encode_point(cls, point: Point | None) -> dict:
        '''
        Encode a `Point` to 0.6 format.

        >>> cls.encode_point(Point(1, 2))
        {'@lon': 1, '@lat': 2}
        '''

        if not point:
            return {}

        return {
            XAttr('lon'): point.x,
            XAttr('lat'): point.y,
        }

    @classmethod
    def decode_point(cls, data: dict) -> Point | None:
        '''
        Decode a point from 0.6 format to `Point`.

        >>> cls.decode_point({'@lon': '1', '@lat': '2'})
        POINT (1 2)
        '''

        if (
            (lon := data.get('@lon')) is None or
            (lat := data.get('@lat')) is None
        ):
            return None

        return Point(
            float(lon),
            float(lat),
        )

    @classmethod
    def encode_nodes(cls, nodes: Sequence[ElementMember]) -> Sequence[dict] | Sequence[SequentialId]:
        '''
        Encode a sequence of `ElementMember` to a sequence in 0.6 format.

        >>> cls.encode_nodes([
        ...     ElementMember(ref=..., role=''),
        ...     ElementMember(ref=..., role=''),
        ... ])
        (
            {'@ref': 1},
            {'@ref': 2}
        )
        '''

        if Format.is_json():
            return tuple(node.ref.id for node in nodes)
        else:
            return tuple(
                {'@ref': node.ref.id}
                for node in nodes)

    @classmethod
    def decode_nodes(cls, nodes: Sequence[dict]) -> Sequence[ElementMember]:
        '''
        Decode a sequence of members from 0.6 format to a sequence of `ElementMember`.

        >>> cls.decode_nodes([
        ...     {'@ref': '1'},
        ...     {'@ref': '2'},
        ... ])
        (
            ElementMember(type=<ElementType.node: 'node'>, ref=1, role=''),
            ElementMember(type=<ElementType.node: 'node'>, ref=2, role='')
        )
        '''

        return tuple(
            ElementMember(
                ref=TypedElementRef(
                    type=ElementType.node,
                    id=int(node['@ref']),
                ),
                role='',
            )
            for node in nodes
        )

    @classmethod
    def encode_members(cls, members: Sequence[ElementMember]) -> Sequence[dict]:
        '''
        Encode a sequence of `ElementMember` to a sequence in 0.6 format.

        >>> cls.encode_members([
        ...     ElementMember(ref=..., role='a'),
        ...     ElementMember(ref=..., role='b'),
        ... ])
        (
            {'@type': 'node', '@ref': 1, '@role': 'a'},
            {'@type': 'way', '@ref': 2, '@role': 'b'}
        )
        '''

        return tuple(
            {
                XAttr('type'): member.ref.type.value,
                XAttr('ref'): member.ref.id,
                XAttr('role'): member.role,
            } for member in members)

    @classmethod
    def decode_members(cls, members: Sequence[dict]) -> Sequence[ElementMember]:
        '''
        Decode a sequence of members from 0.6 format to a sequence of `ElementMember`.

        >>> cls.decode_member([
        ...     {'@type': 'node', '@ref': '1', '@role': 'a'},
        ...     {'@type': 'way', '@ref': '2', '@role': 'b'},
        ... ])
        (
            ElementMember(type=<ElementType.node: 'node'>, ref=1, role='a'),
            ElementMember(type=<ElementType.way: 'way'>, ref=2, role='b')
        )
        '''

        return tuple(
            ElementMember(
                ref=TypedElementRef(
                    type=ElementType.from_str(member['@type']),
                    id=int(member['@ref']),
                ),
                role=member['@role'],
            )
            for member in members
        )

    @classmethod
    def encode_element(cls, element: Element) -> dict:
        '''
        Encode `Element` to 0.6 format.

        >>> cls.encode_element(ElementNode(...))
        {'node': {'@id': 1, '@version': 1, ...}}
        '''

        if Format.is_json():
            return {
                'type': element.type.value,
                'id': element.typed_id,
                **(cls.encode_point(element.point) if element.type == ElementType.node else {}),
                'version': element.version,
                'timestamp': element.created_at,
                'changeset': element.changeset_id,
                'uid': element.user_.id,
                'user': element.user_.display_name,
                'visible': element.visible,
                'tags': element.tags,
                **({'nodes': cls.encode_nodes(element.members)} if element.type == ElementType.way else {}),
                **({'members': cls.encode_members(element.members)} if element.type == ElementType.relation else {}),
            }
        else:
            return {element.type.value: {
                '@id': element.typed_id,
                **(cls.encode_point(element.point) if element.type == ElementType.node else {}),
                '@version': element.version,
                '@timestamp': element.created_at,
                '@changeset': element.changeset_id,
                '@uid': element.user_.id,  # TODO: smart user cache
                '@user': element.user_.display_name,  # TODO: is @user here a mistake?
                '@visible': element.visible,
                'tag': cls.encode_tags(element.tags),
                **({'nd': cls.encode_nodes(element.members)} if element.type == ElementType.way else {}),
                **({'member': cls.encode_members(element.members)} if element.type == ElementType.relation else {}),
            }}

    @classmethod
    def decode_element(cls, element: dict, changeset_id: SequentialId | None) -> Element:
        '''
        Decode an element from 0.6 format to `Element`.

        If `changeset_id` is `None`, it will be extracted from the element data.

        >>> cls.decode_element({'node': {'@id': 1, '@version': 1, ...}})
        ElementNode(...)
        '''

        if len(element) != 1:
            raise ValueError(f'Expected one element, got {len(element)}')

        type, data = next(iter(element.items()))
        type = ElementType.from_str(type)
        data: dict

        if type == ElementType.node:
            element = ElementNode(
                user_id=user.id,
                typed_id=data.get('@id'),
                changeset_id=changeset_id or data.get('@changeset'),
                version=data.get('@version', 0) + 1,
                visible=data.get('@visible', True),
                tags=cls.decode_tags(data.get('tag', [])),
                point=cls.decode_point(data),
            )
        elif type == ElementType.way:
            element = ElementWay(
                user_id=user.id,
                typed_id=data.get('@id'),
                changeset_id=changeset_id or data.get('@changeset'),
                version=data.get('@version', 0) + 1,
                visible=data.get('@visible', True),
                tags=cls.decode_tags(data.get('tag', [])),
                members=cls.decode_nodes(data.get('nd', [])),
            )
        elif type == ElementType.relation:
            element = ElementRelation(
                user_id=user.id,
                typed_id=data.get('@id'),
                changeset_id=changeset_id or data.get('@changeset'),
                version=data.get('@version', 0) + 1,
                visible=data.get('@visible', True),
                tags=cls.decode_tags(data.get('tag', [])),
                members=cls.decode_members(data.get('member', [])),
            )
        else:
            raise NotImplementedError(f'Unsupported element type {type!r}')

        return element

    @classmethod
    def encode_elements(cls, elements: Sequence[Element]) -> dict[str, Sequence[dict]]:
        '''
        Encode a sequence of `Element` to 0.6 format.

        >>> cls.encode_elements([
        ...     ElementNode(...),
        ...     ElementWay(...),
        ... ])
        {'node': [{'@id': 1, '@version': 1, ...}], 'way': [{'@id': 2, '@version': 1, ...}]}
        '''

        if Format.is_json():
            return {'elements': tuple(
                cls.encode_element(element)
                for element in elements
            )}
        else:
            result: dict[str, list[dict]] = defaultdict(list)
            for element in elements:
                result[element.type.value].append(cls.encode_element(element))
            return result

    @classmethod
    def encode_changeset_comment(cls, comment: ChangesetComment) -> dict:
        '''
        Encode `ChangesetComment` to 0.6 format.

        >>> cls.encode_changeset_comment(ChangesetComment(...))
        {'@uid': 1, '@user': ..., '@date': ..., 'text': 'lorem ipsum'}
        '''

        return {
            XAttr('id'): comment.id,
            XAttr('date'): comment.created_at,
            XAttr('uid'): comment.user_.id,  # TODO: user cache
            XAttr('user'): comment.user_.display_name,
            'text': comment.body,
        }

    @classmethod
    def encode_changeset(cls, changeset: Changeset, *, add_comments_count: int = 0) -> dict:
        '''
        Encode `Changeset` to 0.6 format.

        >>> cls.encode_changeset(Changeset(...))
        {'changeset': {'@id': 1, '@created_at': ..., ..., 'discussion': {'comment': [...]}}}
        '''

        if changeset.boundary:
            minx, miny, maxx, maxy = changeset.boundary.bounds
            boundary_d = {
                XAttr('minlon', custom_xml='min_lon'): minx,
                XAttr('minlat', custom_xml='min_lat'): miny,
                XAttr('maxlon', custom_xml='max_lon'): maxx,
                XAttr('maxlat', custom_xml='max_lat'): maxy,
            }
        else:
            boundary_d = {}

        if Format.is_json():
            return {
                'type': 'changeset',
                'id': changeset.id,
                'created_at': changeset.created_at,
                **({'closed_at': changeset.closed_at} if changeset.closed_at else {}),
                'open': not changeset.closed_at,
                'user': changeset.user_.display_name,
                'uid': changeset.user_.id,
                **boundary_d,
                'comments_count': changeset.comments_count_ + add_comments_count,
                'changes_count': changeset.size,
                'tags': changeset.tags,
                **({'discussion': tuple(
                    cls.encode_changeset_comment(comment)
                    for comment in changeset.comments_
                )} if changeset.comments_ is not None else {}),
            }
        else:
            return {'changeset': {
                '@id': changeset.id,
                '@created_at': changeset.created_at,
                **({'@closed_at': changeset.closed_at} if changeset.closed_at else {}),
                '@open': not changeset.closed_at,
                '@user': changeset.user_.display_name,
                '@uid': changeset.user_.id,
                **boundary_d,
                '@comments_count': changeset.comments_count_ + add_comments_count,
                '@changes_count': changeset.size,
                'tag': cls.encode_tags(changeset.tags),
                **({'discussion': {
                    'comment': tuple(
                        cls.encode_changeset_comment(comment)
                        for comment in changeset.comments_),
                }} if changeset.comments_ is not None else {}),
            }}

    @classmethod
    def encode_changesets(cls, changesets: Sequence[Changeset]) -> dict:
        '''
        Encode a sequence of `Changeset` to 0.6 format.

        >>> cls.encode_changesets([
        ...     Changeset(...),
        ...     Changeset(...),
        ... ])
        {'changeset': [{'@id': 1, '@created_at': ..., ..., 'discussion': {'comment': [...]}}]}
        '''

        if Format.is_json():
            return {'elements': tuple(
                cls.encode_changeset(changeset)
                for changeset in changesets
            )}
        else:
            return {'changeset': tuple(
                cls.encode_changeset(changeset)['changeset']
                for changeset in changesets
            )}

    @classmethod
    def encode_osmchange(cls, changes: Sequence[Element]) -> Sequence[tuple[str, dict]]:
        '''
        Encode a sequence of `Element` to a sequence in 0.6 format.

        >>> cls.encode_osmchange([
        ...     ElementNode(...),
        ...     ElementWay(...),
        ... ])
        [
            ('create', {'node': [{'@id': 1, '@version': 1, ...}]}),
            ('modify', {'way': [{'@id': 2, '@version': 2, ...}]}),
        ]
        '''

        result = [None] * len(changes)
        for i, element in len(changes):
            if element.version == 1:
                action = OSMChangeAction.create.value
            elif element.visible:
                action = OSMChangeAction.modify.value
            else:
                action = OSMChangeAction.delete.value
            result[i] = (action, cls.encode_element(element))
        return result

    @classmethod
    def decode_osmchange(cls, elements: Sequence[tuple[str, dict]], changeset_id: SequentialId | None) -> Sequence[Element]:
        '''
        Decode a sequence of changes from 0.6 format to a sequence of `Element`.

        If `changeset_id` is `None`, it will be extracted from the element data.

        >>> cls.decode_osmchange([
        ...     ('create', {'node': [{'@id': 1, '@version': 1, ...}]}),
        ...     ('modify', {'way': [{'@id': 2, '@version': 2, ...}]}),
        ... ])
        [
            ElementNode(...),
            ElementWay(...),
        ]
        '''

        result = [None] * len(elements)
        for i, (action, element_d) in len(elements):
            if len(element_d) != 1:
                raise ValueError(f'Expected one element in {action!r}, got {len(element_d)}')

            element = cls.decode_element(element_d, changeset_id)

            if action == OSMChangeAction.create.value:
                if element.id > 0:
                    Exceptions.get().raise_for_diff_create_bad_id(element.versioned_ref)
                if element.version > 1:
                    element = element.model_copy(update={'version': 1})
            elif action == OSMChangeAction.modify.value:
                if element.version < 2:
                    Exceptions.get().raise_for_diff_update_bad_version(element.versioned_ref)
            elif action == OSMChangeAction.delete.value:
                if element.version < 2:
                    Exceptions.get().raise_for_diff_update_bad_version(element.versioned_ref)
                if element.visible:
                    element = element.model_copy(update={'visible': False})
            else:
                Exceptions.get().raise_for_diff_unsupported_action(action)

            result[i] = element
        return result

    @classmethod
    def encode_diff_result(cls, old_ref_elements_map: dict[TypedElementRef, Sequence[Element]]) -> dict:
        '''
        Encode a diff result to 0.6 format.

        >>> cls.encode_diff_result({
        ...     TypedElementRef(type=ElementType.node, id=-1): [
        ...         ElementNode(typed_id=1, version=1, ...),
        ...         ElementNode(typed_id=1, version=2, ...),
        ...     ],
        ... })
        [
            ('node', {'@old_id': -1, '@new_id': 1, '@new_version': 1}),
            ('node', {'@old_id': -1, '@new_id': 1, '@new_version': 2})
        ]
        '''

        result = []
        for typed_ref, elements in old_ref_elements_map.items():
            for element in elements:
                result.append((
                    typed_ref.type.value,
                    {
                        '@old_id': typed_ref.id,
                        '@new_id': element.typed_id,
                        '@new_version': element.version,
                    },
                ))
        return result

    @classmethod
    def encode_gpx(cls, trackpoints: Sequence[TracePoint]) -> dict:
        '''
        Encode a sequence of `TracePoint` to GPX 1.0 format.

        >>> cls.encode_gpx([
        ...     TracePoint(...),
        ...     TracePoint(...),
        ... ])
        {'gpx': {'trk': [{'trkseg': [{'trkpt': [{'@lon': 1, '@lat': 2}, {'@lon': 3, '@lat': 4}]}]}]}
        '''

        trks = []
        trk_trksegs = []
        trk_trkseg_trkpts = []

        last_trk_id = None
        last_trkseg_id = None

        for point in trackpoints:
            if point.trace_.visibility in (TraceVisibility.identifiable, TraceVisibility.trackable):
                if last_trk_id != point.trace_id:
                    if point.trace_.visibility == TraceVisibility.identifiable:
                        user: User = point.trace_.user_id  # TODO: user load
                        url = f'/user/{user.display_name}/traces/{point.trace_id}'
                    else:
                        url = None

                    trk_trksegs = []
                    trks.append({
                        'name': point.trace_.name,
                        'desc': point.trace_.description,
                        **({'url': url} if url else {}),
                        'trkseg': trk_trksegs,
                    })
                    last_trk_id = point.trace_id
                    last_trkseg_id = None

                if last_trkseg_id != point.track_idx:
                    trk_trkseg_trkpts = []
                    trk_trksegs.append({'trkpt': trk_trkseg_trkpts})
                    last_trkseg_id = point.track_idx

                trk_trkseg_trkpts.append({
                    **cls.encode_point(point.point),
                    **({'ele': point.elevation} if point.elevation is not None else {}),
                    'time': point.captured_at,
                })
        else:
            if last_trk_id is not None or last_trkseg_id is not None:
                trk_trksegs = []
                trks.append({'trkseg': trk_trksegs})
                trk_trkseg_trkpts = []
                trk_trksegs.append({'trkpt': trk_trkseg_trkpts})
                last_trk_id = None
                last_trkseg_id = None

            trk_trkseg_trkpts.append(cls.encode_point(point.point))

        return {
            'gpx': {
                '@version': '1.0',
                '@creator': GENERATOR,
                '@xmlns': 'http://www.topografix.com/GPX/1/0',
                'trk': trks,
            },
        }

    @classmethod
    def decode_gpx(cls, gpx: dict) -> Sequence[TracePoint]:
        '''
        Decode a GPX 1.0 format to a sequence of `TracePoint`.

        Returns a sequence of points, with tracks and segments flattened.

        >>> cls.decode_gpx({'gpx': {'trk': [{'trkseg': [{'trkpt': [{'@lon': 1, '@lat': 2}, {'@lon': 3, '@lat': 4}]}]}]}})
        [
            TracePoint(...),
            TracePoint(...),
        ]
        '''

        tracks = gpx.get('gpx', {}).get('trk', [])
        result = []

        for trk in tracks:
            for track_idx, trkseg in enumerate(trk.get('trkseg', [])):
                for trkpt in trkseg.get('trkpt', []):
                    trkpt: dict

                    captured_at = datetime.fromisoformat(time) if (time := trkpt.get('time')) else None
                    point = cls.decode_point(trkpt)
                    elevation = trkpt.get('ele')

                    result.append(TracePoint(
                        track_idx=track_idx,
                        captured_at=captured_at,
                        point=point,
                        elevation=elevation,
                    ))

        return result

    @classmethod
    def encode_gpx_file(cls, trace: Trace) -> dict:
        '''
        Encode a `Trace` to 0.6 format.

        >>> cls.encode_gpx_file(Trace(...))
        {'gpx_file': {'@id': 1, '@uid': 1234, ...}}
        '''

        return {
            'gpx_file': {
                '@id': trace.id,
                '@uid': trace.user_id,
                '@user': trace.user_id.display_name,  # TODO: user load
                '@timestamp': trace.created_at,
                '@name': trace.name,
                '@lon': trace.start_point.x,
                '@lat': trace.start_point.y,
                '@visibility': trace.visibility.value,
                '@pending': False,
                'description': trace.description,
                'tag': trace.tags,
            }
        }

    @classmethod
    def encode_gpx_files(cls, traces: Sequence[Trace]) -> dict:
        '''
        Encode a sequence of `Trace` to 0.6 format.

        >>> cls.encode_gpx_files([
        ...     Trace(...),
        ...     Trace(...),
        ... ])
        {'gpx_file': [{'@id': 1, '@uid': 1234, ...}, {'@id': 2, '@uid': 1234, ...}]}
        '''

        return {
            'gpx_file': tuple(
                cls.encode_gpx_file(trace)
                for trace in traces
            ),
        }

    @classmethod
    def decode_gpx_file(cls, gpx_file: dict) -> Trace:
        '''
        Decode a GPX file from 0.6 format to `Trace`.
        '''

        return Trace(
            user_id=user.id,
            name=gpx_file.get('@name'),
            description=gpx_file.get('description'),
            size=1,
            start_point=Point(
                float(gpx_file.get('@lon', 0)),
                float(gpx_file.get('@lat', 0)),
            ),
            visibility=TraceVisibility(gpx_file.get('@visibility')),
            created_at=datetime.fromisoformat(timestamp) if (timestamp := gpx_file.get('@timestamp')) else utcnow(),
            tags=gpx_file.get('tag', []),
        )

    @classmethod
    def encode_note_comment(cls, comment: NoteComment) -> dict:
        '''
        Encode `NoteComment` to 0.6 format.

        >>> cls.encode_note_comment(NoteComment(...))
        {'date': '2019-06-15 08:26:04 UTC', 'uid': 1234, 'user': 'userName', ...}
        '''

        return {
            'date': format_sql_date(comment.created_at),
            'uid': comment.user_id,
            'user': comment.user.display_name,  # TODO: user load
            'user_url': f'{BASE_URL}/user/{comment.user.display_name}',
            'action': comment.event.value,
            'text': comment.body,
            'html': f'<p>{html.escape(comment.body)}</p>' if comment.body else '',
        }

    @classmethod
    def encode_note(cls, note: Note) -> dict:
        '''
        Encode `Note` to 0.6 format.

        >>> cls.encode_note(Note(...))
        {'@lon': 0.1, '@lat': 51, 'id': 16659, ...}
        '''

        if Format.is_json():
            return {
                'type': 'Feature',
                'geometry': mapping(note.point),
                'properties': {
                    'id': note.id,
                    'url': f'{BASE_URL}/api/0.6/notes/{note.id}.json',
                    **({
                        'reopen_url': f'{BASE_URL}/api/0.6/notes/{note.id}/reopen.json',
                    } if note.closed_at else {
                        'comment_url': f'{BASE_URL}/api/0.6/notes/{note.id}/comment.json',
                        'close_url': f'{BASE_URL}/api/0.6/notes/{note.id}/close.json',
                    }),
                    'date_created': format_sql_date(note.created_at),
                    'status': 'hidden' if note.hidden_at else ('closed' if note.closed_at else 'open'),
                    **({'closed_at': format_sql_date(note.closed_at)} if note.closed_at else {}),
                    'comments': tuple(
                        cls.encode_note_comment(comment)
                        for comment in note.comments_)
                }
            }
        else:
            return {
                **cls.encode_point(note.point),
                'id': note.id,
                'url': f'{BASE_URL}/api/0.6/notes/{note.id}',
                **({
                    'reopen_url': f'{BASE_URL}/api/0.6/notes/{note.id}/reopen',
                } if note.closed_at else {
                    'comment_url': f'{BASE_URL}/api/0.6/notes/{note.id}/comment',
                    'close_url': f'{BASE_URL}/api/0.6/notes/{note.id}/close',
                }),
                'date_created': format_sql_date(note.created_at),
                'status': 'hidden' if note.hidden_at else ('closed' if note.closed_at else 'open'),
                **({'closed_at': format_sql_date(note.closed_at)} if note.closed_at else {}),
                'comments': {
                    'comment': tuple(
                        cls.encode_note_comment(comment)
                        for comment in note.comments_
                    ),
                },
            }

    @classmethod
    def encode_notes(cls, notes: Sequence[Note]) -> dict:
        '''
        Encode a sequence of `Note` to 0.6 format.

        >>> cls.encode_notes([
        ...     Note(...),
        ...     Note(...),
        ... ])
        {'note': [{'@lon': 1, '@lat': 2, 'id': 1, ...}]}
        '''

        if Format.is_json():
            return {
                'type': 'FeatureCollection',
                'features': tuple(
                    cls.encode_note(note)
                    for note in notes)
            }
        else:
            return {'note': tuple(
                cls.encode_note(note)
                for note in notes
            )}

    @classmethod
    def encode_languages(cls, languages: Sequence[str]) -> dict | Sequence[str]:
        '''
        Encode a sequence of languages to 0.6 format.

        >>> cls.encode_languages(['en', 'pl'])
        {'lang': ('en', 'pl')}
        '''

        if Format.is_json():
            return tuple(languages)
        else:
            return {'lang': tuple(languages)}

    @classmethod
    def encode_user(cls, user: User) -> dict:
        '''
        Encode a `User` to 0.6 format.

        >>> cls.encode_user(User(...))
        {'user': {'@id': 1234, '@display_name': 'userName', ...}}
        '''

        current_user: User | None = Auth.user()
        access_private = current_user and current_user.id == user.id

        return {'user': {
            XAttr('id'): user.id,
            XAttr('display_name'): user.display_name,
            XAttr('account_created'): user.created_at,
            'description': user.description,
            ('contributor_terms' if Format.is_json() else 'contributor-terms'): {
                XAttr('agreed'): bool(user.terms_accepted_at),
                **({
                    XAttr('pd'): user.consider_public_domain
                } if access_private else {}),
            },
            'img': {
                XAttr('href'): user.avatar_url
            },
            'roles': [role.value for role in user.roles],
            'changesets': {
                XAttr('count'): 0  # TODO: changesets count
            },
            'traces': {
                XAttr('count'): 0  # TODO: traces count
            },
            'blocks': {
                'received': {
                    XAttr('count'): 0,  # TODO: blocks count
                    XAttr('active'): 0,
                },
                'issued': {
                    XAttr('count'): 0,  # TODO: blocks count
                    XAttr('active'): 0,
                },
            },

            # private section
            **({
                **({'home': {
                    **cls.encode_point(user.home_point),
                    XAttr('zoom'): user.home_zoom,
                }} if user.home_point else {}),
                'languages': cls.encode_languages(user.languages),
                'messages': {
                    'received': {
                        XAttr('count'): 0,
                        XAttr('unread'): 0
                    },  # TODO: messages count
                    'sent': {
                        XAttr('count'): 0
                    },
                },
            } if access_private else {}),
        }}

    @classmethod
    def encode_users(cls, users: Sequence[User]) -> dict:
        '''
        Encode a sequence of `User` to 0.6 format.

        >>> cls.encode_users([
        ...     User(...),
        ...     User(...),
        ... ])
        {'user': [{'@id': 1234, '@display_name': 'userName', ...}]}
        '''

        if Format.is_json():
            return {'users': tuple(
                cls.encode_user(user)
                for user in users
            )}
        else:
            return {'user': tuple(
                cls.encode_changeset(user)['user']
                for user in users
            )}
