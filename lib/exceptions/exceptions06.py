from collections.abc import Sequence
from datetime import datetime
from typing import NoReturn

from fastapi import status
from humanize import naturalsize

from lib.exceptions.exceptions_base import ExceptionsBase
from limits import (
    MAP_QUERY_AREA_MAX_SIZE,
    MAP_QUERY_LEGACY_NODES_LIMIT,
    NOTE_QUERY_AREA_MAX_SIZE,
    TRACE_POINT_QUERY_AREA_MAX_SIZE,
)
from models.element_type import ElementType
from models.oauth2_code_challenge_method import OAuth2CodeChallengeMethod
from models.typed_element_ref import TypedElementRef
from models.versioned_element_ref import VersionedElementRef
from utils import format_iso_date


class Exceptions06(ExceptionsBase):
    @classmethod
    def unauthorized(cls, *, request_basic_auth: bool = False) -> NoReturn:
        raise cls.APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail="Couldn't authenticate you",
            headers={'WWW-Authenticate': 'Basic realm="Access to OpenStreetMap API"'} if request_basic_auth else None,
        )

    @classmethod
    def insufficient_scopes(cls, scopes: Sequence[str]) -> NoReturn:
        raise cls.APIError(
            status.HTTP_403_FORBIDDEN,
            detail=f'The request requires higher privileges than authorized ({", ".join(scopes)})',
        )

    @classmethod
    def bad_basic_auth_format(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_400_BAD_REQUEST, detail='Malformed basic auth credentials')

    @classmethod
    def bad_geometry(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_400_BAD_REQUEST)

    @classmethod
    def bad_geometry_coordinates(cls, _: float, __: float) -> NoReturn:
        raise cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='The latitudes must be between -90 and 90, longitudes between -180 and 180 and the minima must be less than the maxima.',
        )

    @classmethod
    def bad_bbox(cls, _: str, __: str | None = None) -> NoReturn:
        raise cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='The parameter bbox is required, and must be of the form min_lon,min_lat,max_lon,max_lat.',
        )

    @classmethod
    def bad_xml(cls, name: str, message: str, xml_input: str) -> NoReturn:
        raise cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Cannot parse valid {name} from xml string {xml_input}. {message}',
        )

    @classmethod
    def input_too_big(cls, size: int) -> NoReturn:
        raise cls.APIError(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f'Request entity too large: {naturalsize(size, True)}',
        )

    @classmethod
    def avatar_not_found(cls, avatar_id: str) -> NoReturn:
        raise cls.APIError(status.HTTP_404_NOT_FOUND, detail=f'Avatar {avatar_id!r} not found')

    @classmethod
    def avatar_too_big(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Avatar is too big')

    @classmethod
    def user_not_found(cls, name_or_id: str | int) -> NoReturn:
        raise cls.APIError(status.HTTP_404_NOT_FOUND, detail=f'User {name_or_id} not known')

    @classmethod
    def user_not_found_bad_request(cls, name_or_id: str | int) -> NoReturn:
        raise cls.APIError(status.HTTP_400_BAD_REQUEST, detail=f'User {name_or_id} not known')

    @classmethod
    def changeset_not_found(cls, changeset_id: int) -> NoReturn:
        raise cls.APIError(status.HTTP_404_NOT_FOUND, detail=f'The changeset with the id {changeset_id} was not found')

    @classmethod
    def changeset_access_denied(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_409_CONFLICT, detail="The user doesn't own that changeset")

    @classmethod
    def changeset_not_closed(cls, changeset_id: int) -> NoReturn:
        raise cls.APIError(status.HTTP_409_CONFLICT, detail=f'The changeset {changeset_id} is not yet closed')

    @classmethod
    def changeset_already_closed(cls, changeset_id: int, closed_at: datetime) -> NoReturn:
        raise cls.APIError(
            status.HTTP_409_CONFLICT,
            detail=f'The changeset {changeset_id} was closed at {format_iso_date(closed_at)}',
        )

    @classmethod
    def changeset_not_subscribed(cls, changeset_id: int) -> NoReturn:
        raise cls.APIError(status.HTTP_404_NOT_FOUND, detail=f'You are not subscribed to changeset {changeset_id}.')

    @classmethod
    def changeset_already_subscribed(cls, changeset_id: int) -> NoReturn:
        raise cls.APIError(
            status.HTTP_409_CONFLICT,
            detail=f'The user is already subscribed to changeset {changeset_id}',
        )

    @classmethod
    def changeset_too_big(cls, size: int) -> NoReturn:
        raise cls.APIError(
            status.HTTP_412_PRECONDITION_FAILED,
            detail=f'Changeset size {size} is too big. Please split your changes into multiple changesets.',
        )

    @classmethod
    def changeset_comment_not_found(cls, comment_id: int) -> NoReturn:
        raise cls.APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'The changeset comment with the id {comment_id} was not found',
        )

    @classmethod
    def element_not_found(cls, element_ref: VersionedElementRef | TypedElementRef) -> NoReturn:
        raise cls.APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'The {element_ref.type} with the id {element_ref.typed_id} was not found',
        )

    @classmethod
    def element_already_deleted(cls, versioned_ref: VersionedElementRef) -> NoReturn:
        raise cls.APIError(
            status.HTTP_412_PRECONDITION_FAILED,
            detail=f'Cannot delete an already deleted {versioned_ref.type} with id {versioned_ref.typed_id}.',
        )

    @classmethod
    def element_changeset_missing(cls) -> NoReturn:
        raise cls.APIError(
            status.HTTP_409_CONFLICT,
            detail='You need to supply a changeset to be able to make a change',
        )

    @classmethod
    def element_version_conflict(cls, versioned_ref: VersionedElementRef, local_version: int) -> NoReturn:
        raise cls.APIError(
            status.HTTP_409_CONFLICT,
            detail=f'Version mismatch: Provided {versioned_ref.version - 1}, server had: {local_version} of {versioned_ref.type} {versioned_ref.typed_id}',
        )

    @classmethod
    def element_member_not_found(cls, initiator_ref: VersionedElementRef, member_ref: TypedElementRef) -> NoReturn:
        if initiator_ref.type == ElementType.way:
            raise cls.APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail=f'Way {initiator_ref.typed_id} requires the nodes with id in ({member_ref.typed_id}), which either do not exist, or are not visible.',
            )
        elif initiator_ref.type == ElementType.relation:
            raise cls.APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail=f'Relation with id {initiator_ref.typed_id} cannot be saved due to {member_ref.type} with id {member_ref.typed_id}',
            )
        else:
            raise NotImplementedError(f'Unsupported element type {initiator_ref.type!r}')

    @classmethod
    def element_in_use(cls, versioned_ref: VersionedElementRef, used_by: Sequence[TypedElementRef]) -> NoReturn:
        # wtf is this
        if versioned_ref.type == ElementType.node:
            if ref_ways := tuple(ref for ref in used_by if ref.type == ElementType.way):
                raise cls.APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'Node {versioned_ref.typed_id} is still used by ways {",".join(str(ref.typed_id) for ref in ref_ways)}.',
                )
            elif ref_relations := tuple(ref for ref in used_by if ref.type == ElementType.relation):
                raise cls.APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'Node {versioned_ref.typed_id} is still used by relations {",".join(str(ref.typed_id) for ref in ref_relations)}.',
                )
            else:
                raise NotImplementedError(f'Unsupported element type {next(iter(used_by)).type!r}')
        elif versioned_ref.type == ElementType.way:
            if ref_relations := tuple(ref for ref in used_by if ref.type == ElementType.relation):
                raise cls.APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'Way {versioned_ref.typed_id} is still used by relations {",".join(str(ref.typed_id) for ref in ref_relations)}.',
                )
            else:
                raise NotImplementedError(f'Unsupported element type {next(iter(used_by)).type!r}')
        elif versioned_ref.type == ElementType.relation:
            if ref_relations := tuple(ref for ref in used_by if ref.type == ElementType.relation):
                raise cls.APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'The relation {versioned_ref.typed_id} is used in relation '
                    f'{ref_relations[0].typed_id}.',
                )
            else:
                raise NotImplementedError(f'Unsupported element type {next(iter(used_by)).type!r}')
        else:
            raise NotImplementedError(f'Unsupported element type {versioned_ref.type!r}')

    @classmethod
    def diff_multiple_changesets(cls) -> NoReturn:
        raise cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='Only one changeset can be modified at a time',
        )

    @classmethod
    def diff_unsupported_action(cls, action: str) -> NoReturn:
        raise cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Unknown action {action}, choices are create, modify, delete',
        )

    @classmethod
    def diff_create_bad_id(cls, versioned_ref: VersionedElementRef) -> NoReturn:
        if versioned_ref.type == ElementType.node:
            raise cls.APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail='Cannot create node: data is invalid.',
            )
        elif versioned_ref.type == ElementType.way:
            raise cls.APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail='Cannot create way: data is invalid.',
            )
        elif versioned_ref.type == ElementType.relation:
            raise cls.APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail='Cannot create relation: data or member data is invalid.',
            )
        else:
            raise NotImplementedError(f'Unsupported element type {versioned_ref.type.type!r}')

    @classmethod
    def diff_update_bad_version(cls, versioned_ref: VersionedElementRef) -> NoReturn:
        raise cls.APIError(
            status.HTTP_412_PRECONDITION_FAILED,
            detail=f'Update action requires version >= 1, got {versioned_ref.version - 1}',
        )

    @classmethod
    def element_redacted(cls, versioned_ref: VersionedElementRef) -> NoReturn:
        # TODO: 0.7 legal reasons
        return cls.element_not_found(versioned_ref)

    @classmethod
    def redact_latest_version(cls) -> NoReturn:
        raise cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='Cannot redact current version of element, only historical versions may be redacted',
        )

    @classmethod
    def oauth1_timestamp_out_of_range(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_400_BAD_REQUEST, detail='OAuth timestamp out of range')

    @classmethod
    def oauth1_nonce_missing(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_400_BAD_REQUEST, detail='OAuth nonce missing')

    @classmethod
    def oauth1_bad_nonce(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_400_BAD_REQUEST, detail='OAuth nonce invalid')

    @classmethod
    def oauth1_nonce_used(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_401_UNAUTHORIZED, detail='OAuth nonce already used')

    @classmethod
    def oauth1_bad_verifier(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_401_UNAUTHORIZED, detail='OAuth verifier invalid')

    @classmethod
    def oauth1_unsupported_signature_method(cls, method: str) -> NoReturn:
        raise cls.APIError(status.HTTP_400_BAD_REQUEST, detail=f'OAuth unsupported signature method {method!r}')

    @classmethod
    def oauth1_bad_signature(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_401_UNAUTHORIZED, detail='OAuth signature invalid')

    @classmethod
    def oauth2_bearer_missing(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_401_UNAUTHORIZED, detail='OAuth2 bearer authorization header missing')

    @classmethod
    def oauth2_challenge_method_not_set(cls) -> NoReturn:
        raise cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='OAuth2 verifier provided but code challenge method is not set',
        )

    @classmethod
    def oauth2_bad_verifier(cls, code_challenge_method: OAuth2CodeChallengeMethod) -> NoReturn:
        raise cls.APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail=f'OAuth2 verifier invalid for {code_challenge_method.value} code challenge method',
        )

    @classmethod
    def oauth_bad_app_token(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_401_UNAUTHORIZED, detail='OAuth application token invalid')

    @classmethod
    def oauth_bad_user_token(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_401_UNAUTHORIZED, detail='OAuth user token invalid')

    @classmethod
    def oauth_bad_redirect_uri(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_400_BAD_REQUEST, detail='OAuth redirect uri invalid')

    @classmethod
    def oauth_bad_scopes(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_400_BAD_REQUEST, detail='OAuth scopes invalid')

    @classmethod
    def map_query_area_too_big(cls) -> NoReturn:
        raise cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'The maximum bbox size is {MAP_QUERY_AREA_MAX_SIZE}, and your request was too large. Either request a smaller area, or use planet.osm',
        )

    @classmethod
    def map_query_nodes_limit_exceeded(cls) -> NoReturn:
        raise cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'You requested too many nodes (limit is {MAP_QUERY_LEGACY_NODES_LIMIT}). Either request a smaller area, or use planet.osm',
        )

    @classmethod
    def notes_query_area_too_big(cls) -> NoReturn:
        raise cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'The maximum bbox size is {NOTE_QUERY_AREA_MAX_SIZE}, and your request was too large. Please request a smaller area.',
        )

    @classmethod
    def trace_not_found(cls, _: int) -> NoReturn:
        raise cls.APIError(status.HTTP_404_NOT_FOUND)

    @classmethod
    def trace_access_denied(cls, _: int) -> NoReturn:
        raise cls.APIError(status.HTTP_403_FORBIDDEN)

    @classmethod
    def trace_points_query_area_too_big(cls) -> NoReturn:
        raise cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'The maximum bbox size is {TRACE_POINT_QUERY_AREA_MAX_SIZE}, and your request was too large. Please request a smaller area.',
        )

    @classmethod
    def trace_file_unsupported_format(cls, content_type: str) -> NoReturn:
        raise cls.APIError(status.HTTP_400_BAD_REQUEST, detail=f'Unsupported trace file format {content_type!r}')

    @classmethod
    def trace_file_archive_too_deep(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Trace file archive is too deep')

    @classmethod
    def trace_file_archive_corrupted(cls, content_type: str) -> NoReturn:
        raise cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Trace file archive failed to decompress {content_type!r}',
        )

    @classmethod
    def trace_file_archive_too_many_files(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Trace file archive contains too many files')

    @classmethod
    def bad_trace_file(cls, message: str) -> NoReturn:
        raise cls.APIError(status.HTTP_400_BAD_REQUEST, detail=f'Failed to parse trace file: {message}')

    @classmethod
    def note_not_found(cls, _: int) -> NoReturn:
        raise cls.APIError(status.HTTP_404_NOT_FOUND)

    @classmethod
    def note_closed(cls, note_id: int, closed_at: datetime) -> NoReturn:
        raise cls.APIError(
            status.HTTP_409_CONFLICT,
            detail=f'The note {note_id} was closed at {format_iso_date(closed_at)}',
        )

    @classmethod
    def note_open(cls, note_id: int) -> NoReturn:
        raise cls.APIError(status.HTTP_409_CONFLICT, detail=f'The note {note_id} is already open')
