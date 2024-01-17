from collections.abc import Sequence
from datetime import datetime
from typing import NoReturn, override

from fastapi import status
from humanize import naturalsize

from app.lib.exceptions import APIError, Exceptions
from app.limits import (
    MAP_QUERY_AREA_MAX_SIZE,
    MAP_QUERY_LEGACY_NODES_LIMIT,
    NOTE_QUERY_AREA_MAX_SIZE,
    TRACE_POINT_QUERY_AREA_MAX_SIZE,
    USER_PREF_BULK_SET_LIMIT,
)
from app.models.element_type import ElementType
from app.models.oauth2_code_challenge_method import OAuth2CodeChallengeMethod
from app.models.typed_element_ref import TypedElementRef
from app.models.versioned_element_ref import VersionedElementRef
from app.utils import format_iso_date


class Exceptions06(Exceptions):
    @override
    def unauthorized(self, *, request_basic_auth: bool = False) -> NoReturn:
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail="Couldn't authenticate you",
            headers={'WWW-Authenticate': 'Basic realm="Access to OpenStreetMap API"'} if request_basic_auth else None,
        )

    @override
    def insufficient_scopes(self, scopes: Sequence[str]) -> NoReturn:
        raise APIError(
            status.HTTP_403_FORBIDDEN,
            detail=f'The request requires higher privileges than authorized ({", ".join(scopes)})',
        )

    @override
    def bad_basic_auth_format(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='Malformed basic auth credentials',
        )

    @override
    def bad_geometry(self) -> NoReturn:
        raise APIError(status.HTTP_400_BAD_REQUEST)

    @override
    def bad_geometry_coordinates(self, _: float, __: float) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='The latitudes must be between -90 and 90, longitudes between -180 and 180 and the minima must be less than the maxima.',
        )

    @override
    def bad_bbox(self, _: str, __: str | None = None) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='The parameter bbox is required, and must be of the form min_lon,min_lat,max_lon,max_lat.',
        )

    @override
    def bad_xml(self, name: str, message: str, xml_input: str) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Cannot parse valid {name} from xml string {xml_input}. {message}',
        )

    @override
    def input_too_big(self, size: int) -> NoReturn:
        raise APIError(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f'Request entity too large: {naturalsize(size, True)}',
        )

    @override
    def avatar_not_found(self, avatar_id: str) -> NoReturn:
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'Avatar {avatar_id!r} not found',
        )

    @override
    def avatar_too_big(self) -> NoReturn:
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Avatar is too big',
        )

    @override
    def user_not_found(self, name_or_id: str | int) -> NoReturn:
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'User {name_or_id} not known',
        )

    @override
    def user_not_found_bad_request(self, name_or_id: str | int) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'User {name_or_id} not known',
        )

    @override
    def changeset_not_found(self, changeset_id: int) -> NoReturn:
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'The changeset with the id {changeset_id} was not found',
        )

    @override
    def changeset_access_denied(self) -> NoReturn:
        raise APIError(
            status.HTTP_409_CONFLICT,
            detail="The user doesn't own that changeset",
        )

    @override
    def changeset_not_closed(self, changeset_id: int) -> NoReturn:
        raise APIError(
            status.HTTP_409_CONFLICT,
            detail=f'The changeset {changeset_id} is not yet closed',
        )

    @override
    def changeset_already_closed(self, changeset_id: int, closed_at: datetime) -> NoReturn:
        raise APIError(
            status.HTTP_409_CONFLICT,
            detail=f'The changeset {changeset_id} was closed at {format_iso_date(closed_at)}',
        )

    @override
    def changeset_not_subscribed(self, changeset_id: int) -> NoReturn:
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'You are not subscribed to changeset {changeset_id}.',
        )

    @override
    def changeset_already_subscribed(self, changeset_id: int) -> NoReturn:
        raise APIError(
            status.HTTP_409_CONFLICT,
            detail=f'The user is already subscribed to changeset {changeset_id}',
        )

    @override
    def changeset_too_big(self, size: int) -> NoReturn:
        raise APIError(
            status.HTTP_412_PRECONDITION_FAILED,
            detail=f'Changeset size {size} is too big. Please split your changes into multiple changesets.',
        )

    @override
    def changeset_comment_not_found(self, comment_id: int) -> NoReturn:
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'The changeset comment with the id {comment_id} was not found',
        )

    @override
    def element_not_found(self, element_ref: VersionedElementRef | TypedElementRef) -> NoReturn:
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'The {element_ref.type} with the id {element_ref.typed_id} was not found',
        )

    @override
    def element_already_deleted(self, versioned_ref: VersionedElementRef) -> NoReturn:
        raise APIError(
            status.HTTP_412_PRECONDITION_FAILED,
            detail=f'Cannot delete an already deleted {versioned_ref.type} with id {versioned_ref.typed_id}.',
        )

    @override
    def element_changeset_missing(self) -> NoReturn:
        raise APIError(
            status.HTTP_409_CONFLICT,
            detail='You need to supply a changeset to be able to make a change',
        )

    @override
    def element_version_conflict(self, versioned_ref: VersionedElementRef, local_version: int) -> NoReturn:
        raise APIError(
            status.HTTP_409_CONFLICT,
            detail=f'Version mismatch: Provided {versioned_ref.version - 1}, server had: {local_version} of {versioned_ref.type} {versioned_ref.typed_id}',
        )

    @override
    def element_member_not_found(self, initiator_ref: VersionedElementRef, member_ref: TypedElementRef) -> NoReturn:
        if initiator_ref.type == ElementType.way:
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail=f'Way {initiator_ref.typed_id} requires the nodes with id in ({member_ref.typed_id}), which either do not exist, or are not visible.',
            )
        elif initiator_ref.type == ElementType.relation:
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail=f'Relation with id {initiator_ref.typed_id} cannot be saved due to {member_ref.type} with id {member_ref.typed_id}',
            )
        else:
            raise NotImplementedError(f'Unsupported element type {initiator_ref.type!r}')

    @override
    def element_in_use(self, versioned_ref: VersionedElementRef, used_by: Sequence[TypedElementRef]) -> NoReturn:
        # wtf is this
        if versioned_ref.type == ElementType.node:
            if ref_ways := tuple(ref for ref in used_by if ref.type == ElementType.way):
                raise APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'Node {versioned_ref.typed_id} is still used by ways {",".join(str(ref.typed_id) for ref in ref_ways)}.',
                )
            elif ref_relations := tuple(ref for ref in used_by if ref.type == ElementType.relation):
                raise APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'Node {versioned_ref.typed_id} is still used by relations {",".join(str(ref.typed_id) for ref in ref_relations)}.',
                )
            else:
                raise NotImplementedError(f'Unsupported element type {next(iter(used_by)).type!r}')
        elif versioned_ref.type == ElementType.way:
            if ref_relations := tuple(ref for ref in used_by if ref.type == ElementType.relation):
                raise APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'Way {versioned_ref.typed_id} is still used by relations {",".join(str(ref.typed_id) for ref in ref_relations)}.',
                )
            else:
                raise NotImplementedError(f'Unsupported element type {next(iter(used_by)).type!r}')
        elif versioned_ref.type == ElementType.relation:
            if ref_relations := tuple(ref for ref in used_by if ref.type == ElementType.relation):
                raise APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'The relation {versioned_ref.typed_id} is used in relation '
                    f'{ref_relations[0].typed_id}.',
                )
            else:
                raise NotImplementedError(f'Unsupported element type {next(iter(used_by)).type!r}')
        else:
            raise NotImplementedError(f'Unsupported element type {versioned_ref.type!r}')

    @override
    def diff_multiple_changesets(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='Only one changeset can be modified at a time',
        )

    @override
    def diff_unsupported_action(self, action: str) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Unknown action {action}, choices are create, modify, delete',
        )

    @override
    def diff_create_bad_id(self, versioned_ref: VersionedElementRef) -> NoReturn:
        if versioned_ref.type == ElementType.node:
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail='Cannot create node: data is invalid.',
            )
        elif versioned_ref.type == ElementType.way:
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail='Cannot create way: data is invalid.',
            )
        elif versioned_ref.type == ElementType.relation:
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail='Cannot create relation: data or member data is invalid.',
            )
        else:
            raise NotImplementedError(f'Unsupported element type {versioned_ref.type.type!r}')

    @override
    def diff_update_bad_version(self, versioned_ref: VersionedElementRef) -> NoReturn:
        raise APIError(
            status.HTTP_412_PRECONDITION_FAILED,
            detail=f'Update action requires version >= 1, got {versioned_ref.version - 1}',
        )

    @override
    def element_redacted(self, versioned_ref: VersionedElementRef) -> NoReturn:
        # TODO: 0.7 legal reasons
        return self.element_not_found(versioned_ref)

    @override
    def redact_latest_version(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='Cannot redact current version of element, only historical versions may be redacted',
        )

    @override
    def oauth1_timestamp_out_of_range(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='OAuth timestamp out of range',
        )

    @override
    def oauth1_nonce_missing(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='OAuth nonce missing',
        )

    @override
    def oauth1_bad_nonce(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='OAuth nonce invalid',
        )

    @override
    def oauth1_nonce_used(self) -> NoReturn:
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail='OAuth nonce already used',
        )

    @override
    def oauth1_bad_verifier(self) -> NoReturn:
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail='OAuth verifier invalid',
        )

    @override
    def oauth1_unsupported_signature_method(self, method: str) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'OAuth unsupported signature method {method!r}',
        )

    @override
    def oauth1_bad_signature(self) -> NoReturn:
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail='OAuth signature invalid',
        )

    @override
    def oauth2_bearer_missing(self) -> NoReturn:
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail='OAuth2 bearer authorization header missing',
        )

    @override
    def oauth2_challenge_method_not_set(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='OAuth2 verifier provided but code challenge method is not set',
        )

    @override
    def oauth2_bad_verifier(self, code_challenge_method: OAuth2CodeChallengeMethod) -> NoReturn:
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail=f'OAuth2 verifier invalid for {code_challenge_method.value} code challenge method',
        )

    @override
    def oauth_bad_app_token(self) -> NoReturn:
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail='OAuth application token invalid',
        )

    @override
    def oauth_bad_user_token(self) -> NoReturn:
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail='OAuth user token invalid',
        )

    @override
    def oauth_bad_redirect_uri(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='OAuth redirect uri invalid',
        )

    @override
    def oauth_bad_scopes(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='OAuth scopes invalid',
        )

    @override
    def map_query_area_too_big(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'The maximum bbox size is {MAP_QUERY_AREA_MAX_SIZE}, and your request was too large. Either request a smaller area, or use planet.osm',
        )

    @override
    def map_query_nodes_limit_exceeded(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'You requested too many nodes (limit is {MAP_QUERY_LEGACY_NODES_LIMIT}). Either request a smaller area, or use planet.osm',
        )

    @override
    def notes_query_area_too_big(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'The maximum bbox size is {NOTE_QUERY_AREA_MAX_SIZE}, and your request was too large. Please request a smaller area.',
        )

    @override
    def trace_not_found(self, _: int) -> NoReturn:
        raise APIError(status.HTTP_404_NOT_FOUND)

    @override
    def trace_access_denied(self, _: int) -> NoReturn:
        raise APIError(status.HTTP_403_FORBIDDEN)

    @override
    def trace_points_query_area_too_big(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'The maximum bbox size is {TRACE_POINT_QUERY_AREA_MAX_SIZE}, and your request was too large. Please request a smaller area.',
        )

    @override
    def trace_file_unsupported_format(self, content_type: str) -> NoReturn:
        raise APIError(status.HTTP_400_BAD_REQUEST, detail=f'Unsupported trace file format {content_type!r}')

    @override
    def trace_file_archive_too_deep(self) -> NoReturn:
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Trace file archive is too deep',
        )

    @override
    def trace_file_archive_corrupted(self, content_type: str) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Trace file archive failed to decompress {content_type!r}',
        )

    @override
    def trace_file_archive_too_many_files(self) -> NoReturn:
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Trace file archive contains too many files',
        )

    @override
    def bad_trace_file(self, message: str) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Failed to parse trace file: {message}',
        )

    @override
    def note_not_found(self, _: int) -> NoReturn:
        raise APIError(status.HTTP_404_NOT_FOUND)

    @override
    def note_closed(self, note_id: int, closed_at: datetime) -> NoReturn:
        raise APIError(
            status.HTTP_409_CONFLICT,
            detail=f'The note {note_id} was closed at {format_iso_date(closed_at)}',
        )

    @override
    def note_open(self, note_id: int) -> NoReturn:
        raise APIError(
            status.HTTP_409_CONFLICT,
            detail=f'The note {note_id} is already open',
        )

    @override
    def pref_not_found(self, _: int | None, key: str) -> NoReturn:
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'Preference {key!r} not found',
        )

    @override
    def pref_duplicate_key(self, key: str) -> NoReturn:
        raise APIError(
            status.HTTP_406_NOT_ACCEPTABLE,
            detail=f'Duplicate preferences with key {key}',
        )

    @override
    def pref_bulk_set_limit_exceeded(self) -> NoReturn:
        raise APIError(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f'Too many preferences (limit is {USER_PREF_BULK_SET_LIMIT})',
        )
