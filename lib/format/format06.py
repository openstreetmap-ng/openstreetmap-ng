import html
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime

from shapely.geometry import Point, mapping

from config import BASE_URL, GENERATOR
from cython_lib.xmltodict import XAttr
from lib.auth import auth_user
from lib.exceptions import exceptions
from lib.format import format_is_json
from models.db.changeset import Changeset
from models.db.changeset_comment import ChangesetComment
from models.db.element import Element
from models.db.note import Note
from models.db.note_comment import NoteComment
from models.db.trace_ import Trace
from models.db.trace_point import TracePoint
from models.db.user import User
from models.element_member import ElementMember
from models.element_type import ElementType
from models.osmchange_action import OSMChangeAction
from models.trace_visibility import TraceVisibility
from models.typed_element_ref import TypedElementRef
from models.validating.element import ElementValidating
from models.validating.trace_ import TraceValidating
from models.validating.trace_point import TracePointValidating
from utils import format_sql_date


class Format06:
    @classmethod
    def encode_tags(cls, tags: dict) -> Sequence[dict] | dict:
        if format_is_json():
            return tags
        else:
            return tuple({'@k': k, '@v': v} for k, v in tags.items())

    @classmethod
    def decode_tags(cls, tags: Sequence[dict]) -> dict:
        """
        >>> cls.decode_tags([
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

    @classmethod
    def encode_point(cls, point: Point | None) -> dict:
        """
        >>> cls.encode_point(Point(1, 2))
        {'@lon': 1, '@lat': 2}
        """

        if not point:
            return {}

        return {
            XAttr('lon'): point.x,
            XAttr('lat'): point.y,
        }

    @classmethod
    def decode_point(cls, data: dict) -> Point | None:
        """
        >>> cls.decode_point({'@lon': '1', '@lat': '2'})
        POINT (1 2)
        """

        if (lon := data.get('@lon')) is None or (lat := data.get('@lat')) is None:
            return None

        return Point(
            float(lon),
            float(lat),
        )

    @classmethod
    def encode_nodes(cls, nodes: Sequence[ElementMember]) -> Sequence[dict] | Sequence[int]:
        """
        >>> cls.encode_nodes([
        ...     ElementMember(type=ElementType.node, typed_id=1, role=''),
        ...     ElementMember(type=ElementType.node, typed_id=2, role=''),
        ... ])
        ({'@ref': 1}, {'@ref': 2})
        """

        if format_is_json():
            return tuple(node.typed_id for node in nodes)
        else:
            return tuple({'@ref': node.typed_id} for node in nodes)

    @classmethod
    def decode_nodes(cls, nodes: Sequence[dict]) -> Sequence[ElementMember]:
        return tuple(
            ElementMember(
                type=ElementType.node,
                typed_id=int(node['@ref']),
                role='',
            )
            for node in nodes
        )

    @classmethod
    def encode_members(cls, members: Sequence[ElementMember]) -> Sequence[dict]:
        """
        >>> cls.encode_members([
        ...     ElementMember(type=ElementType.node, typed_id=1, role='a'),
        ...     ElementMember(type=ElementType.way, typed_id=2, role='b'),
        ... ])
        (
            {'@type': 'node', '@ref': 1, '@role': 'a'},
            {'@type': 'way', '@ref': 2, '@role': 'b'}
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

    @classmethod
    def decode_members(cls, members: Sequence[dict]) -> Sequence[ElementMember]:
        return tuple(
            ElementMember(
                type=ElementType.from_str(member['@type']),
                typed_id=int(member['@ref']),
                role=member['@role'],
            )
            for member in members
        )

    @classmethod
    def encode_element(cls, element: Element) -> dict:
        """
        >>> cls.encode_element(Element(type=ElementType.node, typed_id=1, version=1, ...))
        {'node': {'@id': 1, '@version': 1, ...}}
        """

        if format_is_json():
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
            return {
                element.type.value: {
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
                }
            }

    @classmethod
    def decode_element(cls, element: dict, changeset_id: int | None) -> Element:
        """
        If `changeset_id` is `None`, it will be extracted from the element data.
        """

        if len(element) != 1:
            raise ValueError(f'Expected one root element, got {len(element)}')

        user = auth_user()
        type, data = next(iter(element.items()))
        type = ElementType.from_str(type)
        data: dict

        return Element(
            **ElementValidating(
                user_id=user.id,
                changeset_id=changeset_id or data.get('@changeset'),
                type=type,
                typed_id=data.get('@id'),
                version=data.get('@version', 0) + 1,
                visible=data.get('@visible', True),
                tags=cls.decode_tags(data.get('tag', ())),
                point=cls.decode_point(data),
                members=cls.decode_nodes(data.get('nd', cls.decode_members(data.get('member', ())))),
            ).to_orm_dict()
        )

    @classmethod
    def encode_elements(cls, elements: Sequence[Element]) -> dict[str, Sequence[dict]]:
        """
        >>> cls.encode_elements([
        ...     Element(type=ElementType.node, typed_id=1, version=1, ...),
        ...     Element(type=ElementType.way, typed_id=2, version=1,
        ... ])
        {'node': [{'@id': 1, '@version': 1, ...}], 'way': [{'@id': 2, '@version': 1, ...}]}
        """

        # TODO: multiprocessing batch?

        if format_is_json():
            return {'elements': tuple(cls.encode_element(element) for element in elements)}
        else:
            result: dict[str, list[dict]] = defaultdict(list)
            for element in elements:
                result[element.type.value].append(cls.encode_element(element))
            return result

    @classmethod
    def encode_changeset_comment(cls, comment: ChangesetComment) -> dict:
        """
        >>> cls.encode_changeset_comment(ChangesetComment(...))
        {'@uid': 1, '@user': ..., '@date': ..., 'text': 'lorem ipsum'}
        """

        return {
            XAttr('id'): comment.id,
            XAttr('date'): comment.created_at,
            XAttr('uid'): comment.user_.id,  # TODO: user cache
            XAttr('user'): comment.user_.display_name,
            'text': comment.body,
        }

    @classmethod
    def encode_changeset(cls, changeset: Changeset, *, add_comments_count: int = 0) -> dict:
        """
        >>> cls.encode_changeset(Changeset(...))
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

        if format_is_json():
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
                **(
                    {'discussion': tuple(cls.encode_changeset_comment(comment) for comment in changeset.comments_)}
                    if changeset.comments_ is not None
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
                    '@user': changeset.user_.display_name,
                    '@uid': changeset.user_.id,
                    **boundary_d,
                    '@comments_count': changeset.comments_count_ + add_comments_count,
                    '@changes_count': changeset.size,
                    'tag': cls.encode_tags(changeset.tags),
                    **(
                        {
                            'discussion': {
                                'comment': tuple(
                                    cls.encode_changeset_comment(comment) for comment in changeset.comments_
                                ),
                            }
                        }
                        if changeset.comments_ is not None
                        else {}
                    ),
                }
            }

    @classmethod
    def encode_changesets(cls, changesets: Sequence[Changeset]) -> dict:
        """
        >>> cls.encode_changesets([
        ...     Changeset(...),
        ...     Changeset(...),
        ... ])
        {'changeset': [{'@id': 1, '@created_at': ..., ..., 'discussion': {'comment': [...]}}]}
        """

        if format_is_json():
            return {'elements': tuple(cls.encode_changeset(changeset) for changeset in changesets)}
        else:
            return {'changeset': tuple(cls.encode_changeset(changeset)['changeset'] for changeset in changesets)}

    @classmethod
    def encode_osmchange(cls, changes: Sequence[Element]) -> Sequence[tuple[str, dict]]:
        """
        >>> cls.encode_osmchange([
        ...     Element(type=ElementType.node, typed_id=1, version=1, ...),
        ...     Element(type=ElementType.way, typed_id=2, version=2, ...)
        ... ])
        [
            ('create', {'node': [{'@id': 1, '@version': 1, ...}]}),
            ('modify', {'way': [{'@id': 2, '@version': 2, ...}]}),
        ]
        """

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
    def decode_osmchange(cls, elements: Sequence[tuple[str, dict]], changeset_id: int | None) -> Sequence[Element]:
        """
        If `changeset_id` is `None`, it will be extracted from the element data.

        >>> cls.decode_osmchange([
        ...     ('create', {'node': [{'@id': 1, '@version': 1, ...}]}),
        ...     ('modify', {'way': [{'@id': 2, '@version': 2, ...}]}),
        ... ])
        [Element(type=ElementType, ...), Element(type=ElementType.way, ...)]
        """

        result = [None] * len(elements)
        for i, (action, element_d) in len(elements):
            if len(element_d) != 1:
                raise ValueError(f'Expected one element in {action!r}, got {len(element_d)}')

            element = cls.decode_element(element_d, changeset_id)

            if action == OSMChangeAction.create.value:
                if element.id > 0:
                    exceptions().raise_for_diff_create_bad_id(element.versioned_ref)
                if element.version > 1:
                    element.version = 1
            elif action == OSMChangeAction.modify.value:
                if element.version < 2:
                    exceptions().raise_for_diff_update_bad_version(element.versioned_ref)
            elif action == OSMChangeAction.delete.value:
                if element.version < 2:
                    exceptions().raise_for_diff_update_bad_version(element.versioned_ref)
                if element.visible:
                    element.visible = False
            else:
                exceptions().raise_for_diff_unsupported_action(action)

            result[i] = element
        return result

    @classmethod
    def encode_diff_result(cls, old_ref_elements_map: dict[TypedElementRef, Sequence[Element]]) -> Sequence[tuple]:
        """
        >>> cls.encode_diff_result({
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
            for typed_ref, elements in old_ref_elements_map.items()
            for element in elements
        )

    @classmethod
    def encode_gpx(cls, trace_points: Sequence[TracePoint]) -> dict:
        """
        >>> cls.encode_gpx([
        ...     TracePoint(...),
        ...     TracePoint(...),
        ... ])
        {'gpx': {'trk': [{'trkseg': [{'trkpt': [{'@lon': 1, '@lat': 2}, {'@lon': 3, '@lat': 4}]}]}]}
        """

        trks = []
        trk_trksegs = []
        trk_trkseg_trkpts = []

        last_trk_id = None
        last_trkseg_id = None

        for tp in trace_points:
            if tp.trace_.visibility in (TraceVisibility.identifiable, TraceVisibility.trackable):
                if last_trk_id != tp.trace_id:
                    if tp.trace_.visibility == TraceVisibility.identifiable:
                        user: User = tp.trace_.user_id  # TODO: user load
                        url = f'/user/{user.display_name}/traces/{tp.trace_id}'
                    else:
                        url = None

                    trk_trksegs = []
                    trks.append(
                        {
                            'name': tp.trace_.name,
                            'desc': tp.trace_.description,
                            **({'url': url} if url else {}),
                            'trkseg': trk_trksegs,
                        }
                    )
                    last_trk_id = tp.trace_id
                    last_trkseg_id = None

                if last_trkseg_id != tp.track_idx:
                    trk_trkseg_trkpts = []
                    trk_trksegs.append({'trkpt': trk_trkseg_trkpts})
                    last_trkseg_id = tp.track_idx

                trk_trkseg_trkpts.append(
                    {
                        **cls.encode_point(tp.point),
                        **({'ele': tp.elevation} if tp.elevation is not None else {}),
                        'time': tp.captured_at,
                    }
                )
        else:
            if last_trk_id is not None or last_trkseg_id is not None:
                trk_trksegs = []
                trks.append({'trkseg': trk_trksegs})
                trk_trkseg_trkpts = []
                trk_trksegs.append({'trkpt': trk_trkseg_trkpts})
                last_trk_id = None
                last_trkseg_id = None

            trk_trkseg_trkpts.append(cls.encode_point(tp.point))

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
        """
        >>> cls.decode_gpx({'gpx': {'trk': [{'trkseg': [{'trkpt': [{'@lon': 1, '@lat': 2}]}]}]}})
        [TracePoint(...)]
        """

        tracks = gpx.get('gpx', {}).get('trk', [])
        result = []

        for trk in tracks:
            trk: dict
            for track_idx, trkseg in enumerate(trk.get('trkseg', [])):
                trkseg: dict
                for trkpt in trkseg.get('trkpt', []):
                    trkpt: dict

                    result.append(
                        TracePoint(
                            **TracePointValidating(
                                track_idx=track_idx,
                                captured_at=datetime.fromisoformat(time) if (time := trkpt.get('time')) else None,
                                point=cls.decode_point(trkpt),
                                elevation=trkpt.get('ele'),
                            ).to_orm_dict()
                        )
                    )

        return result

    @classmethod
    def encode_gpx_file(cls, trace: Trace) -> dict:
        """
        >>> cls.encode_gpx_file(Trace(...))
        {'gpx_file': {'@id': 1, '@uid': 1234, ...}}
        """

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
        """
        >>> cls.encode_gpx_files([
        ...     Trace(...),
        ...     Trace(...),
        ... ])
        {'gpx_file': [{'@id': 1, '@uid': 1234, ...}, {'@id': 2, '@uid': 1234, ...}]}
        """

        return {
            'gpx_file': tuple(cls.encode_gpx_file(trace) for trace in traces),
        }

    @classmethod
    def decode_gpx_file(cls, gpx_file: dict) -> Trace:
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

    @classmethod
    def encode_note_comment(cls, comment: NoteComment) -> dict:
        """
        >>> cls.encode_note_comment(NoteComment(...))
        {'date': '2019-06-15 08:26:04 UTC', 'uid': 1234, 'user': 'userName', ...}
        """

        return {
            'date': format_sql_date(comment.created_at),
            'uid': comment.user_id,
            'user': comment.user.display_name,  # TODO: user load
            'user_url': f'{BASE_URL}/user/{comment.user.display_name}',
            'action': comment.event.value,
            'text': comment.body,
            'html': f'<p>{html.escape(comment.body)}</p>' if comment.body else '',  # a disaster waiting to happen
        }

    @classmethod
    def encode_note(cls, note: Note) -> dict:
        """
        >>> cls.encode_note(Note(...))
        {'@lon': 0.1, '@lat': 51, 'id': 16659, ...}
        """

        if format_is_json():
            return {
                'type': 'Feature',
                'geometry': mapping(note.point),
                'properties': {
                    'id': note.id,
                    'url': f'{BASE_URL}/api/0.6/notes/{note.id}.json',
                    **(
                        {
                            'reopen_url': f'{BASE_URL}/api/0.6/notes/{note.id}/reopen.json',
                        }
                        if note.closed_at
                        else {
                            'comment_url': f'{BASE_URL}/api/0.6/notes/{note.id}/comment.json',
                            'close_url': f'{BASE_URL}/api/0.6/notes/{note.id}/close.json',
                        }
                    ),
                    'date_created': format_sql_date(note.created_at),
                    'status': 'hidden' if note.hidden_at else ('closed' if note.closed_at else 'open'),
                    **({'closed_at': format_sql_date(note.closed_at)} if note.closed_at else {}),
                    'comments': tuple(cls.encode_note_comment(comment) for comment in note.comments_),
                },
            }
        else:
            return {
                **cls.encode_point(note.point),
                'id': note.id,
                'url': f'{BASE_URL}/api/0.6/notes/{note.id}',
                **(
                    {
                        'reopen_url': f'{BASE_URL}/api/0.6/notes/{note.id}/reopen',
                    }
                    if note.closed_at
                    else {
                        'comment_url': f'{BASE_URL}/api/0.6/notes/{note.id}/comment',
                        'close_url': f'{BASE_URL}/api/0.6/notes/{note.id}/close',
                    }
                ),
                'date_created': format_sql_date(note.created_at),
                'status': 'hidden' if note.hidden_at else ('closed' if note.closed_at else 'open'),
                **({'closed_at': format_sql_date(note.closed_at)} if note.closed_at else {}),
                'comments': {
                    'comment': tuple(cls.encode_note_comment(comment) for comment in note.comments_),
                },
            }

    @classmethod
    def encode_notes(cls, notes: Sequence[Note]) -> dict:
        """
        >>> cls.encode_notes([
        ...     Note(...),
        ...     Note(...),
        ... ])
        {'note': [{'@lon': 1, '@lat': 2, 'id': 1, ...}]}
        """

        if format_is_json():
            return {'type': 'FeatureCollection', 'features': tuple(cls.encode_note(note) for note in notes)}
        else:
            return {'note': tuple(cls.encode_note(note) for note in notes)}

    @classmethod
    def encode_languages(cls, languages: Sequence[str]) -> dict | Sequence[str]:
        """
        >>> cls.encode_languages(['en', 'pl'])
        {'lang': ('en', 'pl')}
        """

        if format_is_json():
            return tuple(languages)
        else:
            return {'lang': tuple(languages)}

    @classmethod
    def encode_user(cls, user: User) -> dict:
        """
        >>> cls.encode_user(User(...))
        {'user': {'@id': 1234, '@display_name': 'userName', ...}}
        """

        current_user = auth_user()
        access_private = current_user and current_user.id == user.id

        return {
            'user': {
                XAttr('id'): user.id,
                XAttr('display_name'): user.display_name,
                XAttr('account_created'): user.created_at,
                'description': user.description,
                ('contributor_terms' if format_is_json() else 'contributor-terms'): {
                    XAttr('agreed'): bool(user.terms_accepted_at),
                    **({XAttr('pd'): user.consider_public_domain} if access_private else {}),
                },
                'img': {XAttr('href'): user.avatar_url},
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
                **(
                    {
                        **(
                            {
                                'home': {
                                    **cls.encode_point(user.home_point),
                                    XAttr('zoom'): user.home_zoom,
                                }
                            }
                            if user.home_point
                            else {}
                        ),
                        'languages': cls.encode_languages(user.languages),
                        'messages': {
                            'received': {XAttr('count'): 0, XAttr('unread'): 0},  # TODO: messages count
                            'sent': {XAttr('count'): 0},
                        },
                    }
                    if access_private
                    else {}
                ),
            }
        }

    @classmethod
    def encode_users(cls, users: Sequence[User]) -> dict:
        """
        >>> cls.encode_users([
        ...     User(...),
        ...     User(...),
        ... ])
        {'user': [{'@id': 1234, '@display_name': 'userName', ...}]}
        """

        if format_is_json():
            return {'users': tuple(cls.encode_user(user) for user in users)}
        else:
            return {'user': tuple(cls.encode_changeset(user)['user'] for user in users)}
