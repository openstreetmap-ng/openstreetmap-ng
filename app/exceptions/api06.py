"""OSM 0.6 API Exceptions implementation — overrides default error messages
to match the legacy OSM 0.6 wire format expectations.
"""

from collections.abc import Iterable
from datetime import datetime
from typing import TYPE_CHECKING, override

from sizestr import sizestr
from starlette import status

from app.config import (
    MAP_QUERY_AREA_MAX_SIZE,
    MAP_QUERY_LEGACY_NODES_LIMIT,
    NOTE_QUERY_AREA_MAX_SIZE,
    TRACE_POINT_QUERY_AREA_MAX_SIZE,
    USER_PREF_BULK_SET_LIMIT,
)
from app.exceptions.api_error import APIError
from app.exceptions.default import Exceptions
from app.lib.time.date_utils import legacy_date
from app.middlewares.request_context_middleware import get_request
from app.models.element import TypedElementId
from app.models.types import (
    ApplicationId,
    ChangesetCommentId,
    ChangesetId,
    DisplayName,
    NoteId,
    TraceId,
    UserId,
    UserPrefKey,
)
from speedup import element_type, split_typed_element_id, split_typed_element_ids

if TYPE_CHECKING:
    from app.models.db.element import Element, ElementInit
    from app.models.db.oauth2_token import OAuth2CodeChallengeMethod


class Exceptions06(Exceptions):
    # --- auth ---
    @override
    def unauthorized(self, *, request_basic_auth: bool = False):
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail="Couldn't authenticate you",
            headers={'WWW-Authenticate': 'Basic realm="Access to OpenStreetMap API"'}
            if request_basic_auth
            else None,
        )

    @override
    def insufficient_scopes(self, scopes: Iterable[str]):
        raise APIError(
            status.HTTP_403_FORBIDDEN,
            detail=f'The request requires higher privileges than authorized ({", ".join(scopes)})',
        )

    @override
    def bad_basic_auth_format(self):
        raise APIError(
            status.HTTP_400_BAD_REQUEST, detail='Malformed basic auth credentials'
        )

    @override
    def oauth2_bearer_missing(self):
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail='OAuth2 bearer authorization header missing',
        )

    @override
    def oauth2_challenge_method_not_set(self):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='OAuth2 verifier provided but code challenge method is not set',
        )

    @override
    def oauth2_bad_verifier(self, code_challenge_method: OAuth2CodeChallengeMethod):
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail=f'OAuth2 verifier invalid for {code_challenge_method} code challenge method',
        )

    @override
    def oauth_bad_client_secret(self):
        raise APIError(
            status.HTTP_401_UNAUTHORIZED, detail='OAuth application token invalid'
        )

    @override
    def oauth_bad_user_token(self):
        raise APIError(status.HTTP_401_UNAUTHORIZED, detail='OAuth user token invalid')

    @override
    def oauth_bad_redirect_uri(self):
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='OAuth redirect uri invalid')

    @override
    def oauth_bad_scopes(self):
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='OAuth scopes invalid')

    # --- changeset ---
    @override
    def changeset_not_found(self, changeset_id: ChangesetId):
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'The changeset with the id {changeset_id} was not found',
        )

    @override
    def changeset_access_denied(self):
        raise APIError(
            status.HTTP_409_CONFLICT, detail="The user doesn't own that changeset"
        )

    @override
    def changeset_already_closed(self, changeset_id: ChangesetId, closed_at: datetime):
        raise APIError(
            status.HTTP_409_CONFLICT,
            detail=f'The changeset {changeset_id} was closed at {legacy_date(closed_at).isoformat()}',
        )

    @override
    def changeset_not_subscribed(self, changeset_id: ChangesetId):
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'You are not subscribed to changeset {changeset_id}.',
        )

    @override
    def changeset_already_subscribed(self, changeset_id: ChangesetId):
        raise APIError(
            status.HTTP_409_CONFLICT,
            detail=f'The user is already subscribed to changeset {changeset_id}',
        )

    @override
    def changeset_too_big(self, size: int):
        raise APIError(
            status.HTTP_412_PRECONDITION_FAILED,
            detail=f'Changeset size {size} is too big. Please split your changes into multiple changesets.',
        )

    @override
    def changeset_comment_not_found(self, comment_id: ChangesetCommentId):
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'The changeset comment with the id {comment_id} was not found',
        )

    # --- diff ---
    @override
    def diff_multiple_changesets(self):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='Only one changeset can be modified at a time',
        )

    @override
    def diff_unsupported_action(self, action: str):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Unknown action {action}, choices are create, modify, delete',
        )

    @override
    def diff_create_bad_id(self, element: ElementInit):
        type = element_type(element['typed_id'])
        if type == 'node':
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail='Cannot create node: data is invalid.',
            )
        elif type == 'way':
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail='Cannot create way: data is invalid.',
            )
        elif type == 'relation':
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail='Cannot create relation: data or member data is invalid.',
            )
        else:
            raise NotImplementedError(f'Unsupported element type {type!r}')

    @override
    def diff_update_bad_version(self, element: ElementInit):
        raise APIError(
            status.HTTP_412_PRECONDITION_FAILED,
            detail=f'Update action requires version >= 1, got {element["version"] - 1}',
        )

    # --- element ---
    @override
    def element_not_found(
        self, element_ref: TypedElementId | tuple[TypedElementId, int]
    ):
        if isinstance(element_ref, int):
            type, id = split_typed_element_id(element_ref)
        else:
            type, id = split_typed_element_id(element_ref[0])
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'The {type} with the id {id} was not found',
        )

    @override
    def element_redacted(self, versioned_ref: tuple[TypedElementId, int]):
        self.element_not_found(versioned_ref)

    @override
    def element_redact_latest(self):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='Cannot redact current version of element, only historical versions may be redacted',
        )

    @override
    def element_already_deleted(self, element_ref: TypedElementId):
        type, id = split_typed_element_id(element_ref)
        raise APIError(
            status.HTTP_412_PRECONDITION_FAILED,
            detail=f'Cannot delete an already deleted {type} with id {id}.',
        )

    @override
    def element_changeset_missing(self):
        raise APIError(
            status.HTTP_409_CONFLICT,
            detail='You need to supply a changeset to be able to make a change',
        )

    @override
    def element_version_conflict(
        self, element: Element | ElementInit, local_version: int
    ):
        type, id = split_typed_element_id(element['typed_id'])
        raise APIError(
            status.HTTP_409_CONFLICT,
            detail=f'Version mismatch: Provided {element["version"] - 1}, server had: {local_version} of {type} {id}',
        )

    @override
    def element_member_not_found(
        self, parent_ref: TypedElementId, member_ref: TypedElementId
    ):
        parent_type, parent_id = split_typed_element_id(parent_ref)
        member_type, member_id = split_typed_element_id(member_ref)

        if parent_type == 'way':
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail=f'Way {parent_id} requires the nodes with id in ({member_id}), which either do not exist, or are not visible.',
            )

        if parent_type == 'relation':
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail=f'Relation with id {parent_id} cannot be saved due to {member_type} with id {member_id}',
            )

        raise NotImplementedError(f'Unsupported element type {parent_type!r}')

    @override
    def element_in_use(
        self, element_ref: TypedElementId, used_by: list[TypedElementId]
    ):
        type, id = split_typed_element_id(element_ref)
        used_by_type_id = split_typed_element_ids(used_by)

        if type == 'node':
            ref_ways = [type_id for type_id in used_by_type_id if type_id[0] == 'way']
            if ref_ways:
                raise APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'Node {id} is still used by ways {",".join(str(ref[1]) for ref in ref_ways)}.',
                )

            ref_relations = [
                type_id for type_id in used_by_type_id if type_id[0] == 'relation'
            ]
            if ref_relations:
                raise APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'Node {id} is still used by relations {",".join(str(ref[1]) for ref in ref_relations)}.',
                )

            raise NotImplementedError(
                f'Unsupported element type {next(iter(used_by_type_id))[0]!r}'
            )

        if type == 'way':
            ref_relations = [
                type_id for type_id in used_by_type_id if type_id[0] == 'relation'
            ]
            if ref_relations:
                raise APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'Way {id} is still used by relations {",".join(str(ref[1]) for ref in ref_relations)}.',
                )

            raise NotImplementedError(
                f'Unsupported element type {next(iter(used_by_type_id))[0]!r}'
            )

        if type == 'relation':
            ref_relations = [
                type_id for type_id in used_by_type_id if type_id[0] == 'relation'
            ]
            if ref_relations:
                raise APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'The relation {id} is used in relation {ref_relations[0][1]}.',
                )

            raise NotImplementedError(
                f'Unsupported element type {next(iter(used_by_type_id))[0]!r}'
            )

        raise NotImplementedError(f'Unsupported element type {type!r}')

    # --- map ---
    @override
    def map_query_area_too_big(self):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'The maximum bbox size is {MAP_QUERY_AREA_MAX_SIZE}, and your request was too large. Either request a smaller area, or use planet.osm',
        )

    @override
    def map_query_nodes_limit_exceeded(self):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'You requested too many nodes (limit is {MAP_QUERY_LEGACY_NODES_LIMIT}). Either request a smaller area, or use planet.osm',
        )

    # --- note ---
    @override
    def note_closed(self, note_id: NoteId, closed_at: datetime):
        raise APIError(
            status.HTTP_409_CONFLICT,
            detail=f'The note {note_id} was closed at {legacy_date(closed_at).isoformat()}',
        )

    @override
    def note_open(self, note_id: NoteId):
        raise APIError(
            status.HTTP_409_CONFLICT, detail=f'The note {note_id} is already open'
        )

    @override
    def notes_query_area_too_big(self):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'The maximum bbox size is {NOTE_QUERY_AREA_MAX_SIZE}, and your request was too large. Please request a smaller area.',
        )

    # --- request ---
    @override
    def bad_geometry(self):
        raise APIError(status.HTTP_400_BAD_REQUEST)

    @override
    def bad_geometry_coordinates(self):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='The latitudes must be between -90 and 90, longitudes between -180 and 180 and the minima must be less than the maxima.',
        )

    @override
    def bad_bbox(self, bbox: str, condition: str | None = None):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='The parameter bbox is required, and must be of the form min_lon,min_lat,max_lon,max_lat.',
        )

    @override
    def bad_xml(self, name: str, message: str, xml_input: bytes | None = None):
        if xml_input is None:
            xml_input = get_request()._body  # noqa: SLF001
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Cannot parse valid {name} from xml string {xml_input.decode()}. {message}',
        )

    @override
    def input_too_big(self, size: int):
        raise APIError(
            status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f'Request entity too large: {sizestr(size)}',
        )

    # --- trace ---
    @override
    def trace_not_found(self, trace_id: TraceId):
        raise APIError(status.HTTP_404_NOT_FOUND)

    @override
    def trace_access_denied(self, trace_id: TraceId):
        raise APIError(status.HTTP_403_FORBIDDEN)

    @override
    def trace_points_query_area_too_big(self):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'The maximum bbox size is {TRACE_POINT_QUERY_AREA_MAX_SIZE}, and your request was too large. Please request a smaller area.',
        )

    @override
    def trace_file_archive_too_deep(self):
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='Trace file archive is too deep',
        )

    @override
    def trace_file_archive_corrupted(self, content_type: str):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Trace file archive failed to decompress {content_type!r}',
        )

    @override
    def trace_file_archive_too_many_files(self):
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='Trace file archive contains too many files',
        )

    @override
    def bad_trace_file(self, message: str):
        raise APIError(
            status.HTTP_400_BAD_REQUEST, detail=f'Failed to parse trace file: {message}'
        )

    # --- user ---
    @override
    def user_not_found(self, name_or_id: DisplayName | UserId):
        raise APIError(status.HTTP_404_NOT_FOUND, detail=f'User {name_or_id} not known')

    @override
    def user_not_found_bad_request(self, name_or_id: DisplayName | UserId):
        raise APIError(
            status.HTTP_400_BAD_REQUEST, detail=f'User {name_or_id} not known'
        )

    @override
    def pref_not_found(self, app_id: ApplicationId | None, key: UserPrefKey):
        raise APIError(
            status.HTTP_404_NOT_FOUND, detail=f'Preference {key!r} not found'
        )

    @override
    def pref_duplicate_key(self, key: UserPrefKey):
        raise APIError(
            status.HTTP_406_NOT_ACCEPTABLE,
            detail=f'Duplicate preferences with key {key}',
        )

    @override
    def pref_bulk_set_limit_exceeded(self):
        raise APIError(
            status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f'Too many preferences (limit is {USER_PREF_BULK_SET_LIMIT})',
        )
