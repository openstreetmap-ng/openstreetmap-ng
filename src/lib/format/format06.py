from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime

import anyio
import lxml.etree as ET
from shapely.geometry import Point, mapping
from sqlalchemy.exc import InvalidRequestError

from src.config import API_URL
from src.lib.auth import auth_user
from src.lib.exceptions import raise_for
from src.lib.format import format_is_json, format_style
from src.lib.translation import render
from src.lib_cython.xmltodict import XAttr
from src.models.db.changeset import Changeset
from src.models.db.changeset_comment import ChangesetComment
from src.models.db.element import Element
from src.models.db.note import Note
from src.models.db.note_comment import NoteComment
from src.models.db.trace_ import Trace
from src.models.db.trace_point import TracePoint
from src.models.db.user import User
from src.models.db.user_pref import UserPref
from src.models.element_member import ElementMemberRef
from src.models.element_type import ElementType
from src.models.format_style import FormatStyle
from src.models.osmchange_action import OSMChangeAction
from src.models.trace_visibility import TraceVisibility
from src.models.typed_element_ref import TypedElementRef
from src.models.validating.element import ElementValidating
from src.models.validating.tags import TagsValidating
from src.models.validating.trace_ import TraceValidating
from src.models.validating.trace_point import TracePointValidating
from src.models.validating.user_pref import UserPrefValidating
from src.repositories.changeset_repository import ChangesetRepository
from src.repositories.message_repository import MessageRepository
from src.repositories.trace_repository import TraceRepository
from src.repositories.user_block_repository import UserBlockRepository
from src.utils import format_sql_date


class Format06:
    @staticmethod
    def _encode_tags(tags: dict) -> Sequence[dict] | dict:
        if format_is_json():
            return tags
        else:
            return tuple({'@k': k, '@v': v} for k, v in tags.items())

    @staticmethod
    def _decode_tags_unsafe(tags: Sequence[dict]) -> dict:
        """
        This method does not validate the input data.

        >>> _decode_tags_unsafe([
        ...     {'@k': 'a', '@v': '1'},
        ...     {'@k': 'b', '@v': '2'},
        ... ])
        {'a': '1', 'b': '2'}
        """

        items = tuple((tag['@k'], tag['@v']) for tag in tags)
        result = dict(items)

        if len(items) != len(result):
            raise ValueError('Duplicate tags keys')

        return result

    @staticmethod
    def decode_tags_and_validate(tags: Sequence[dict]) -> dict:
        """
        >>> decode_tags_and_validate([
        ...     {'@k': 'a', '@v': '1'},
        ...     {'@k': 'b', '@v': '2'},
        ... ])
        {'a': '1', 'b': '2'}
        """

        return TagsValidating(tags=Format06._decode_tags_unsafe(tags)).tags

    @staticmethod
    def _encode_point(point: Point | None) -> dict:
        """
        >>> _encode_point(Point(1, 2))
        {'@lon': 1, '@lat': 2}
        """

        if not point:
            return {}

        return {
            XAttr('lon'): point.x,
            XAttr('lat'): point.y,
        }

    @staticmethod
    def _decode_point_unsafe(data: dict) -> Point | None:
        """
        This method does not validate the input data.

        >>> _decode_point_unsafe({'@lon': '1', '@lat': '2'})
        POINT (1 2)
        """

        if (lon := data.get('@lon')) is None or (lat := data.get('@lat')) is None:
            return None

        return Point(
            float(lon),
            float(lat),
        )

    @staticmethod
    def _encode_nodes(nodes: Sequence[ElementMemberRef]) -> Sequence[dict] | Sequence[int]:
        """
        >>> _encode_nodes([
        ...     ElementMember(type=ElementType.node, typed_id=1, role=''),
        ...     ElementMember(type=ElementType.node, typed_id=2, role=''),
        ... ])
        ({'@ref': 1}, {'@ref': 2})
        """

        if format_is_json():
            return tuple(node.typed_id for node in nodes)
        else:
            return tuple({'@ref': node.typed_id} for node in nodes)

    @staticmethod
    def _decode_nodes_unsafe(nodes: Sequence[dict]) -> Sequence[ElementMemberRef]:
        """
        This method does not validate the input data.

        >>> _decode_nodes_unsafe([{'@ref': '1'}])
        [ElementMember(type=ElementType.node, typed_id=1, role='')]
        """

        return tuple(
            ElementMemberRef(
                type=ElementType.node,
                typed_id=int(node['@ref']),
                role='',
            )
            for node in nodes
        )

    @staticmethod
    def _encode_members(members: Sequence[ElementMemberRef]) -> Sequence[dict]:
        """
        >>> _encode_members([
        ...     ElementMember(type=ElementType.node, typed_id=1, role='a'),
        ...     ElementMember(type=ElementType.way, typed_id=2, role='b'),
        ... ])
        (
            {'@type': 'node', '@ref': 1, '@role': 'a'},
            {'@type': 'way', '@ref': 2, '@role': 'b'},
        )
        """

        return tuple(
            {
                XAttr('type'): member.type.value,
                XAttr('ref'): member.typed_id,
                XAttr('role'): member.role,
            }
            for member in members
        )

    @staticmethod
    def _decode_members_unsafe(members: Sequence[dict]) -> Sequence[ElementMemberRef]:
        """
        This method does not validate the input data.

        >>> _decode_members_unsafe([
        ...     {'@type': 'node', '@ref': '1', '@role': 'a'},
        ... ])
        [ElementMember(type=ElementType.node, typed_id=1, role='a')]
        """

        return tuple(
            ElementMemberRef(
                type=ElementType.from_str(member['@type']),
                typed_id=int(member['@ref']),
                role=member['@role'],
            )
            for member in members
        )

    @staticmethod
    def encode_element(element: Element) -> dict:
        """
        >>> encode_element(Element(type=ElementType.node, typed_id=1, version=1, ...))
        {'node': {'@id': 1, '@version': 1, ...}}
        """

        if format_is_json():
            return {
                'type': element.type.value,
                'id': element.typed_id,
                **(Format06._encode_point(element.point) if element.type == ElementType.node else {}),
                'version': element.version,
                'timestamp': element.created_at,
                'changeset': element.changeset_id,
                'uid': element.user_id,
                'user': element.user.display_name,
                'visible': element.visible,
                'tags': element.tags,
                **({'nodes': Format06._encode_nodes(element.members)} if element.type == ElementType.way else {}),
                **(
                    {'members': Format06._encode_members(element.members)}
                    if element.type == ElementType.relation
                    else {}
                ),
            }
        else:
            return {
                element.type.value: {
                    '@id': element.typed_id,
                    **(Format06._encode_point(element.point) if element.type == ElementType.node else {}),
                    '@version': element.version,
                    '@timestamp': element.created_at,
                    '@changeset': element.changeset_id,
                    '@uid': element.user_id,
                    '@user': element.user.display_name,
                    '@visible': element.visible,
                    'tag': Format06._encode_tags(element.tags),
                    **({'nd': Format06._encode_nodes(element.members)} if element.type == ElementType.way else {}),
                    **(
                        {'member': Format06._encode_members(element.members)}
                        if element.type == ElementType.relation
                        else {}
                    ),
                }
            }

    @staticmethod
    def decode_element(element: dict, changeset_id: int | None) -> Element:
        """
        If `changeset_id` is `None`, it will be extracted from the element data.
        """

        if len(element) != 1:
            raise ValueError(f'Expected one root element, got {len(element)}')

        type, data = next(iter(element.items()))
        type = ElementType.from_str(type)
        data: dict

        # decode members from either nd or member
        if data_nodes := data.get('nd'):
            members = Format06._decode_nodes_unsafe(data_nodes)
        elif data_members := data.get('member'):
            members = Format06._decode_members_unsafe(data_members)
        else:
            members = ()

        return Element(
            **ElementValidating(
                user_id=auth_user().id,
                changeset_id=changeset_id or data.get('@changeset'),
                type=type,
                typed_id=data.get('@id'),
                version=data.get('@version', 0) + 1,
                visible=data.get('@visible', True),
                tags=Format06._decode_tags_unsafe(data.get('tag', ())),
                point=Format06._decode_point_unsafe(data),
                members=members,
            ).to_orm_dict()
        )

    @staticmethod
    def encode_elements(elements: Sequence[Element]) -> dict[str, Sequence[dict]]:
        """
        >>> encode_elements([
        ...     Element(type=ElementType.node, typed_id=1, version=1, ...),
        ...     Element(type=ElementType.way, typed_id=2, version=1,
        ... ])
        {'node': [{'@id': 1, '@version': 1, ...}], 'way': [{'@id': 2, '@version': 1, ...}]}
        """

        if format_is_json():
            return {'elements': tuple(Format06.encode_element(element) for element in elements)}
        else:
            result: dict[str, list[dict]] = defaultdict(list)
            for element in elements:
                result[element.type.value].append(Format06.encode_element(element))
            return result

    @staticmethod
    def _encode_changeset_comment(comment: ChangesetComment) -> dict:
        """
        >>> _encode_changeset_comment(ChangesetComment(...))
        {'@uid': 1, '@user': ..., '@date': ..., 'text': 'lorem ipsum'}
        """

        return {
            XAttr('id'): comment.id,
            XAttr('date'): comment.created_at,
            XAttr('uid'): comment.user_id,
            XAttr('user'): comment.user.display_name,
            'text': comment.body,
        }

    @staticmethod
    def encode_changeset(changeset: Changeset, *, add_comments_count: int = 0) -> dict:
        """
        >>> encode_changeset(Changeset(...))
        {'changeset': {'@id': 1, '@created_at': ..., ..., 'discussion': {'comment': [...]}}}
        """

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

        try:
            _ = changeset.comments
            has_comments = True
        except InvalidRequestError:
            has_comments = False

        if format_is_json():
            return {
                'type': 'changeset',
                'id': changeset.id,
                'created_at': changeset.created_at,
                **({'closed_at': changeset.closed_at} if changeset.closed_at else {}),
                'open': not changeset.closed_at,
                'uid': changeset.user_id,
                'user': changeset.user.display_name,
                **boundary_d,
                'comments_count': len(changeset.comments) + add_comments_count,
                'changes_count': changeset.size,
                'tags': changeset.tags,
                **(
                    {'discussion': tuple(Format06._encode_changeset_comment(comment) for comment in changeset.comments)}
                    if has_comments
                    else {}
                ),
            }
        else:
            return {
                'changeset': {
                    '@id': changeset.id,
                    '@created_at': changeset.created_at,
                    **({'@closed_at': changeset.closed_at} if changeset.closed_at else {}),
                    '@open': not changeset.closed_at,
                    '@uid': changeset.user_id,
                    '@user': changeset.user.display_name,
                    **boundary_d,
                    '@comments_count': len(changeset.comments) + add_comments_count,
                    '@changes_count': changeset.size,
                    'tag': Format06._encode_tags(changeset.tags),
                    **(
                        {
                            'discussion': {
                                'comment': tuple(
                                    Format06._encode_changeset_comment(comment) for comment in changeset.comments
                                ),
                            }
                        }
                        if has_comments
                        else {}
                    ),
                }
            }

    @staticmethod
    def encode_changesets(changesets: Sequence[Changeset]) -> dict:
        """
        >>> encode_changesets([
        ...     Changeset(...),
        ...     Changeset(...),
        ... ])
        {'changeset': [{'@id': 1, '@created_at': ..., ..., 'discussion': {'comment': [...]}}]}
        """

        if format_is_json():
            return {'elements': tuple(Format06.encode_changeset(changeset) for changeset in changesets)}
        else:
            return {'changeset': tuple(Format06.encode_changeset(changeset)['changeset'] for changeset in changesets)}

    @staticmethod
    def encode_osmchange(elements: Sequence[Element]) -> Sequence[tuple[str, dict]]:
        """
        >>> encode_osmchange([
        ...     Element(type=ElementType.node, typed_id=1, version=1, ...),
        ...     Element(type=ElementType.way, typed_id=2, version=2, ...)
        ... ])
        [
            ('create', {'node': [{'@id': 1, '@version': 1, ...}]}),
            ('modify', {'way': [{'@id': 2, '@version': 2, ...}]}),
        ]
        """

        result = [None] * len(elements)
        for i, element in len(elements):
            if element.version == 1:
                action = OSMChangeAction.create.value
            elif element.visible:
                action = OSMChangeAction.modify.value
            else:
                action = OSMChangeAction.delete.value
            result[i] = (action, Format06.encode_element(element))
        return result

    @staticmethod
    def decode_osmchange(elements: Sequence[tuple[str, dict]], changeset_id: int | None) -> Sequence[Element]:
        """
        If `changeset_id` is `None`, it will be extracted from the element data.

        >>> decode_osmchange([
        ...     ('create', {'node': [{'@id': 1, '@version': 1, ...}]}),
        ...     ('modify', {'way': [{'@id': 2, '@version': 2, ...}]}),
        ... ])
        [Element(type=ElementType, ...), Element(type=ElementType.way, ...)]
        """

        result = [None] * len(elements)

        for i, (action, element_d) in enumerate(elements):
            if len(element_d) != 1:
                raise ValueError(f'Expected one element in {action!r}, got {len(element_d)}')

            element = Format06.decode_element(element_d, changeset_id)

            if action == OSMChangeAction.create.value:
                if element.id > 0:
                    raise_for().diff_create_bad_id(element.versioned_ref)
                if element.version > 1:
                    element.version = 1
            elif action == OSMChangeAction.modify.value:
                if element.version < 2:
                    raise_for().diff_update_bad_version(element.versioned_ref)
            elif action == OSMChangeAction.delete.value:
                if element.version < 2:
                    raise_for().diff_update_bad_version(element.versioned_ref)
                if element.visible:
                    element.visible = False
            else:
                raise_for().diff_unsupported_action(action)

            result[i] = element

        return result

    @staticmethod
    def encode_diff_result(assigned_ref_map: dict[TypedElementRef, Sequence[Element]]) -> Sequence[tuple]:
        """
        >>> encode_diff_result({
        ...     TypedElementRef(type=ElementType.node, typed_id=-1): [
        ...         Element(type=ElementType.node, typed_id=1, version=1, ...),
        ...         Element(type=ElementType.node, typed_id=1, version=2, ...),
        ...     ],
        ... })
        (
            ('node', {'@old_id': -1, '@new_id': 1, '@new_version': 1}),
            ('node', {'@old_id': -1, '@new_id': 1, '@new_version': 2})
        )
        """

        return tuple(
            (
                typed_ref.type.value,
                {
                    '@old_id': typed_ref.typed_id,
                    '@new_id': element.typed_id,
                    '@new_version': element.version,
                },
            )
            for typed_ref, elements in assigned_ref_map.items()
            for element in elements
        )

    @staticmethod
    def encode_tracks(trace_points: Sequence[TracePoint]) -> dict:
        """
        >>> encode_tracks([
        ...     TracePoint(...),
        ...     TracePoint(...),
        ... ])
        {'trk': [{'trkseg': [{'trkpt': [{'@lon': 1, '@lat': 2}, {'@lon': 3, '@lat': 4}]}]}]}
        """

        trks = []
        trk_trksegs = []
        trk_trkseg_trkpts = []

        last_trk_id = None
        last_trkseg_id = None

        for tp in trace_points:
            trace = tp.trace

            # if trace is available via api, encode full information
            if trace.timestamps_via_api:
                # handle track change
                if last_trk_id != trace.id:
                    if trace.visibility == TraceVisibility.identifiable:
                        url = f'/user/permalink/{trace.user_id}/traces/{trace.id}'
                    else:
                        url = None

                    trk_trksegs = []
                    trks.append(
                        {
                            'name': trace.name,
                            'desc': trace.description,
                            **({'url': url} if url else {}),
                            'trkseg': trk_trksegs,
                        }
                    )
                    last_trk_id = trace.id
                    last_trkseg_id = None

                # handle track segment change
                if last_trkseg_id != tp.track_idx:
                    trk_trkseg_trkpts = []
                    trk_trksegs.append({'trkpt': trk_trkseg_trkpts})
                    last_trkseg_id = tp.track_idx

                # add point
                trk_trkseg_trkpts.append(
                    {
                        **Format06._encode_point(tp.point),
                        **({'ele': tp.elevation} if tp.elevation is not None else {}),
                        'time': tp.captured_at,
                    }
                )

            # otherwise, encode only coordinates
            else:
                # handle track and track segment change
                if last_trk_id is not None or last_trkseg_id is not None:
                    trk_trksegs = []
                    trks.append({'trkseg': trk_trksegs})
                    trk_trkseg_trkpts = []
                    trk_trksegs.append({'trkpt': trk_trkseg_trkpts})
                    last_trk_id = None
                    last_trkseg_id = None

                trk_trkseg_trkpts.append(Format06._encode_point(tp.point))

        return {'trk': trks}

    @staticmethod
    def decode_tracks(tracks: Sequence[dict], *, track_idx_start: int = 0) -> Sequence[TracePoint]:
        """
        >>> decode_tracks([{'trkseg': [{'trkpt': [{'@lon': 1, '@lat': 2}]}]}])
        [TracePoint(...)]
        """

        result = []

        for trk in tracks:
            trk: dict
            for track_idx, trkseg in enumerate(trk.get('trkseg', []), track_idx_start):
                trkseg: dict
                for trkpt in trkseg.get('trkpt', []):
                    trkpt: dict

                    result.append(
                        TracePoint(
                            **TracePointValidating(
                                track_idx=track_idx,
                                captured_at=datetime.fromisoformat(time) if (time := trkpt.get('time')) else None,
                                point=Format06._decode_point_unsafe(trkpt),
                                elevation=trkpt.get('ele'),
                            ).to_orm_dict()
                        )
                    )

        return result

    @staticmethod
    def encode_gpx_file(trace: Trace) -> dict:
        """
        >>> encode_gpx_file(Trace(...))
        {'gpx_file': {'@id': 1, '@uid': 1234, ...}}
        """

        return {
            'gpx_file': {
                '@id': trace.id,
                '@uid': trace.user_id,
                '@user': trace.user.display_name,
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

    @staticmethod
    def encode_gpx_files(traces: Sequence[Trace]) -> dict:
        """
        >>> encode_gpx_files([
        ...     Trace(...),
        ...     Trace(...),
        ... ])
        {'gpx_file': [{'@id': 1, '@uid': 1234, ...}, {'@id': 2, '@uid': 1234, ...}]}
        """

        return {
            'gpx_file': tuple(Format06.encode_gpx_file(trace) for trace in traces),
        }

    @staticmethod
    def decode_gpx_file(gpx_file: dict) -> Trace:
        return Trace(
            **TraceValidating(
                user_id=auth_user().id,
                name=gpx_file.get('@name'),
                description=gpx_file.get('description'),
                visibility=TraceVisibility(gpx_file.get('@visibility')),
                size=1,
                start_point=Point(0, 0),
                tags=gpx_file.get('tag', ()),
            ).to_orm_dict()
        )

    @staticmethod
    def _encode_note_comment(comment: NoteComment) -> dict:
        """
        >>> _encode_note_comment(NoteComment(...))
        {'date': '2019-06-15 08:26:04 UTC', 'uid': 1234, 'user': 'userName', ...}
        """

        return {
            'date': format_sql_date(comment.created_at),
            'uid': comment.user_id,
            'user': comment.user.display_name,
            'user_url': comment.user.permalink,
            'action': comment.event.value,
            'text': comment.body,
            'html': comment.body_rich.value,  # a disaster waiting to happen
        }

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
                'geometry': mapping(note.point),
                'properties': {
                    'id': note.id,
                    'url': f'{API_URL}/api/0.6/notes/{note.id}.json',
                    **(
                        {
                            'reopen_url': f'{API_URL}/api/0.6/notes/{note.id}/reopen.json',
                        }
                        if note.closed_at
                        else {
                            'comment_url': f'{API_URL}/api/0.6/notes/{note.id}/comment.json',
                            'close_url': f'{API_URL}/api/0.6/notes/{note.id}/close.json',
                        }
                    ),
                    'date_created': format_sql_date(note.created_at),
                    **({'closed_at': format_sql_date(note.closed_at)} if note.closed_at else {}),
                    'status': note.status.value,
                    'comments': tuple(Format06._encode_note_comment(comment) for comment in note.comments),
                },
            }
        elif style == FormatStyle.gpx:
            return {
                'wpt': {
                    **Format06._encode_point(note.point),
                    'time': note.created_at,
                    'name': f'Note: {note.id}',
                    'link': {'href': note.permalink},
                    'desc': ET.CDATA(render('api/0.6/note_comments_rss.jinja2', comments=note.comments)),
                    'extensions': {
                        'id': note.id,
                        'url': f'{API_URL}/api/0.6/notes/{note.id}.gpx',
                        **(
                            {
                                'reopen_url': f'{API_URL}/api/0.6/notes/{note.id}/reopen.gpx',
                            }
                            if note.closed_at
                            else {
                                'comment_url': f'{API_URL}/api/0.6/notes/{note.id}/comment.gpx',
                                'close_url': f'{API_URL}/api/0.6/notes/{note.id}/close.gpx',
                            }
                        ),
                        'date_created': format_sql_date(note.created_at),
                        **({'date_closed': format_sql_date(note.closed_at)} if note.closed_at else {}),
                        'status': note.status.value,
                    },
                }
            }
        else:
            return {
                'note': {
                    **Format06._encode_point(note.point),
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
                    **({'date_closed': format_sql_date(note.closed_at)} if note.closed_at else {}),
                    'status': note.status.value,
                    'comments': {
                        'comment': tuple(Format06._encode_note_comment(comment) for comment in note.comments),
                    },
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
            return {'type': 'FeatureCollection', 'features': tuple(Format06.encode_note(note) for note in notes)}
        elif style == FormatStyle.gpx:
            return {'wpt': tuple(Format06.encode_note(note)['wpt'] for note in notes)}
        else:
            return {'note': tuple(Format06.encode_note(note)['note'] for note in notes)}

    @staticmethod
    def _encode_languages(languages: Sequence[str]) -> dict | Sequence[str]:
        """
        >>> _encode_languages(['en', 'pl'])
        {'lang': ('en', 'pl')}
        """

        if format_is_json():
            return tuple(languages)
        else:
            return {'lang': tuple(languages)}

    @staticmethod
    async def encode_user(user: User) -> dict:
        """
        >>> encode_user(User(...))
        {'user': {'@id': 1234, '@display_name': 'userName', ...}}
        """

        current_user = auth_user()
        access_private = current_user and current_user.id == user.id

        changesets_count = 0
        traces_count = 0
        block_received_count = 0
        block_received_active_count = 0
        block_issued_count = 0
        block_issued_active_count = 0
        messages_received_count = 0
        messages_received_unread_count = 0
        messages_sent_count = 0

        async def changesets_count_task() -> None:
            nonlocal changesets_count
            changesets_count = await ChangesetRepository.count_by_user_id(user.id)

        async def traces_count_task() -> None:
            nonlocal traces_count
            traces_count = await TraceRepository.count_by_user_id(user.id)

        async def block_received_count_task() -> None:
            nonlocal block_received_count, block_received_active_count
            total, active = await UserBlockRepository.count_received_by_user_id(user.id)
            block_received_count = total
            block_received_active_count = active

        async def block_issued_count_task() -> None:
            nonlocal block_issued_count, block_issued_active_count
            total, active = await UserBlockRepository.count_given_by_user_id(user.id)
            block_issued_count = total
            block_issued_active_count = active

        async def messages_received_count_task() -> None:
            nonlocal messages_received_count, messages_received_unread_count
            total, unread = await MessageRepository.count_received_by_user_id(user.id)
            messages_received_count = total
            messages_received_unread_count = unread

        async def messages_sent_count_task() -> None:
            nonlocal messages_sent_count
            messages_sent_count = await MessageRepository.count_sent_by_user_id(user.id)

        async with anyio.create_task_group() as tg:
            tg.start_soon(changesets_count_task)
            tg.start_soon(traces_count_task)
            tg.start_soon(block_received_count_task)
            tg.start_soon(block_issued_count_task)

            if access_private:
                tg.start_soon(messages_received_count_task)
                tg.start_soon(messages_sent_count_task)

        return {
            'user': {
                XAttr('id'): user.id,
                XAttr('display_name'): user.display_name,
                XAttr('account_created'): user.created_at,
                'description': user.description,
                ('contributor_terms' if format_is_json() else 'contributor-terms'): {
                    XAttr('agreed'): True,
                    **({XAttr('pd'): user.consider_public_domain} if access_private else {}),
                },
                'img': {XAttr('href'): user.avatar_url},
                'roles': [role.value for role in user.roles],
                'changesets': {XAttr('count'): changesets_count},
                'traces': {XAttr('count'): traces_count},
                'blocks': {
                    'received': {
                        XAttr('count'): block_received_count,
                        XAttr('active'): block_received_active_count,
                    },
                    'issued': {
                        XAttr('count'): block_issued_count,
                        XAttr('active'): block_issued_active_count,
                    },
                },
                # private section
                **(
                    {
                        **(
                            {
                                'home': {
                                    **Format06._encode_point(user.home_point),
                                    XAttr('zoom'): 15,  # Default home zoom level
                                }
                            }
                            if user.home_point
                            else {}
                        ),
                        'languages': Format06._encode_languages(user.languages),
                        'messages': {
                            'received': {
                                XAttr('count'): messages_received_count,
                                XAttr('unread'): messages_received_unread_count,
                            },
                            'sent': {XAttr('count'): messages_sent_count},
                        },
                    }
                    if access_private
                    else {}
                ),
            }
        }

    @staticmethod
    async def encode_users(users: Sequence[User]) -> dict:
        """
        >>> encode_users([
        ...     User(...),
        ...     User(...),
        ... ])
        {'user': [{'@id': 1234, '@display_name': 'userName', ...}]}
        """

        encoded = [None] * len(users)

        async def task(i: int, user: User):
            encoded[i] = await Format06.encode_user(user)

        async with anyio.create_task_group() as tg:
            for i, user in enumerate(users):
                tg.start_soon(task, i, user)

        if format_is_json():
            return {'users': tuple(user for user in encoded)}
        else:
            return {'user': tuple(user['user'] for user in encoded)}

    @staticmethod
    def decode_user_preference(pref: dict) -> UserPref:
        """
        >>> decode_user_preference({'@k': 'key', '@v': 'value'})
        UserPref(key='key', value='value')
        """

        return UserPref(
            **UserPrefValidating(
                user_id=auth_user().id,
                app_id=None,  # 0.6 api does not support prefs partitioning
                key=pref['@k'],
                value=pref['@v'],
            ).to_orm_dict()
        )

    @staticmethod
    def decode_user_preferences(prefs: Sequence[dict]) -> Sequence[UserPref]:
        """
        >>> decode_user_preferences([{'@k': 'key', '@v': 'value'}])
        [UserPref(key='key', value='value')]
        """

        seen_keys = set()

        for pref in prefs:
            key = pref['@k']
            if key in seen_keys:
                raise_for().pref_duplicate_key(key)
            seen_keys.add(key)

        return tuple(Format06.decode_user_preference(pref) for pref in prefs)

    @staticmethod
    def encode_user_preferences(prefs: Sequence[UserPref]) -> dict:
        """
        >>> encode_user_preferences([
        ...     UserPref(key='key1', value='value1'),
        ...     UserPref(key='key2', value='value2'),
        ... ])
        {'preferences': {'preference': [{'@k': 'key1', '@v': 'value1'}, {'@k': 'key2', '@v': 'value2'}]}}
        """

        if format_is_json():
            return {
                'preferences': {pref.key: pref.value for pref in prefs},
            }
        else:
            return {
                'preferences': {
                    'preference': tuple(
                        {
                            '@k': pref.key,
                            '@v': pref.value,
                        }
                        for pref in prefs
                    )
                }
            }
