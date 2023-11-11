from abc import ABC
from datetime import datetime
from typing import NoReturn, Sequence

from fastapi import status
from humanize import naturalsize

from lib.exceptions import Exceptions, ExceptionsBase
from limits import (MAP_QUERY_AREA_MAX_SIZE, MAP_QUERY_LEGACY_NODES_LIMIT,
                    NOTE_QUERY_AREA_MAX_SIZE, TRACE_POINT_QUERY_AREA_MAX_SIZE)
from models.db.base_sequential import SequentialId
from models.element_type import ElementType
from models.oauth2_code_challenge_method import OAuth2CodeChallengeMethod
from models.typed_element_ref import TypedElementRef
from models.versioned_element_ref import VersionedElementRef
from utils import format_iso_date


class Exceptions06(ExceptionsBase, ABC):
    @classmethod
    def raise_for_timeout(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_504_GATEWAY_TIMEOUT,
            detail='Request timed out')

    @classmethod
    def raise_for_rate_limit(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail='Too many requests')

    @classmethod
    def raise_for_time_integrity(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Time integrity check failed')

    @classmethod
    def raise_for_bad_cursor(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='Failed to parse database cursor')

    @classmethod
    def raise_for_cursor_expired(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='The database cursor has expired')

    @classmethod
    def raise_for_unauthorized(cls, *, request_basic_auth: bool = False) -> NoReturn:
        return cls.APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail='Couldn\'t authenticate you',
            headers={'WWW-Authenticate': 'Basic realm="Access to OpenStreetMap API"'} if request_basic_auth else None)

    @classmethod
    def raise_for_insufficient_scopes(cls, scopes: Sequence[str]) -> NoReturn:
        return cls.APIError(
            status.HTTP_403_FORBIDDEN,
            detail=f'The request requires higher privileges than authorized ({", ".join(scopes)})')

    @classmethod
    def raise_for_bad_basic_auth_format(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='Malformed basic auth credentials')

    @classmethod
    def raise_for_bad_geometry(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST)

    @classmethod
    def raise_for_bad_geometry_coordinates(cls, lon: float, lat: float) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='The latitudes must be between -90 and 90, longitudes between -180 and 180 and the minima must be less than the maxima.')

    @classmethod
    def raise_for_bad_bbox(cls, bbox: str, condition: str | None = None) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='The parameter bbox is required, and must be of the form min_lon,min_lat,max_lon,max_lat.')

    @classmethod
    def raise_for_bad_xml(cls, name: str, message: str, input: str) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Cannot parse valid {name} from xml string {input}. {message}')

    @classmethod
    def raise_for_input_too_big(cls, size: int) -> NoReturn:
        return cls.APIError(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f'Request entity too large: {naturalsize(size, True)}')

    @classmethod
    def raise_for_user_not_found(cls, name_or_id: str | SequentialId) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'User {name_or_id} not known')

    @classmethod
    def raise_for_changeset_not_found(cls, changeset_id: SequentialId) -> NoReturn:
        return cls.APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'The changeset with the id {changeset_id} was not found')

    @classmethod
    def raise_for_changeset_access_denied(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_409_CONFLICT,
            detail="The user doesn't own that changeset")

    @classmethod
    def raise_for_changeset_not_closed(cls, changeset_id: SequentialId) -> NoReturn:
        return cls.APIError(
            status.HTTP_409_CONFLICT,
            detail=f'The changeset {changeset_id} is not yet closed')

    @classmethod
    def raise_for_changeset_already_closed(cls, changeset_id: SequentialId, closed_at: datetime) -> NoReturn:
        return cls.APIError(
            status.HTTP_409_CONFLICT,
            detail=f'The changeset {changeset_id} was closed at {format_iso_date(closed_at)}')

    @classmethod
    def raise_for_changeset_not_subscribed(cls, changeset_id: SequentialId) -> NoReturn:
        return cls.APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'You are not subscribed to changeset {changeset_id}.')

    @classmethod
    def raise_for_changeset_already_subscribed(cls, changeset_id: SequentialId) -> NoReturn:
        return cls.APIError(
            status.HTTP_409_CONFLICT,
            detail=f'The user is already subscribed to changeset {changeset_id}')

    @classmethod
    def raise_for_changeset_too_big(cls, size: int) -> NoReturn:
        return cls.APIError(
            status.HTTP_412_PRECONDITION_FAILED,
            detail=f'Changeset size {size} is too big. Please split your changes into multiple changesets.')

    @classmethod
    def raise_for_changeset_comment_not_found(cls, comment_id: SequentialId) -> NoReturn:
        return cls.APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'The changeset comment with the id {comment_id} was not found')

    @classmethod
    def raise_for_element_not_found(cls, element_ref: VersionedElementRef | TypedElementRef) -> NoReturn:
        return cls.APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'The {element_ref.type} with the id {element_ref.id} was not found')

    @classmethod
    def raise_for_element_already_deleted(cls, versioned_ref: VersionedElementRef) -> NoReturn:
        return cls.APIError(
            status.HTTP_412_PRECONDITION_FAILED,
            detail=f'Cannot delete an already deleted {versioned_ref.type} with id {versioned_ref.id}.')

    @classmethod
    def raise_for_element_changeset_missing(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_409_CONFLICT,
            detail=f'You need to supply a changeset to be able to make a change')

    @classmethod
    def raise_for_element_version_conflict(cls, versioned_ref: VersionedElementRef, local_version: int) -> NoReturn:
        return cls.APIError(
            status.HTTP_409_CONFLICT,
            detail=f'Version mismatch: Provided {versioned_ref.version - 1}, '
                   f'server had: {local_version} of {versioned_ref.type} {versioned_ref.id}')

    @classmethod
    def raise_for_element_member_not_found(cls, initiator_ref: VersionedElementRef, member_ref: TypedElementRef) -> NoReturn:
        if initiator_ref.type == ElementType.way:
            raise cls.APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail=f'Way {initiator_ref.id} requires the nodes with id in ({member_ref.id}), '
                       f'which either do not exist, or are not visible.')
        elif initiator_ref.type == ElementType.relation:
            raise cls.APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail=f'Relation with id {initiator_ref.id} cannot be saved due to '
                       f'{member_ref.type} with id {member_ref.id}')
        else:
            raise NotImplementedError(f'Unsupported element type {initiator_ref.type!r}')

    @classmethod
    def raise_for_element_in_use(cls, versioned_ref: VersionedElementRef, used_by: Sequence[TypedElementRef]) -> NoReturn:
        # wtf is this
        if versioned_ref.type == ElementType.node:
            if ref_ways := tuple(ref for ref in used_by if ref.type == ElementType.way):
                raise cls.APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'Node {versioned_ref.id} is still used by ways '
                           f'{",".join(str(ref.id) for ref in ref_ways)}.')
            elif ref_relations := tuple(ref for ref in used_by if ref.type == ElementType.relation):
                raise cls.APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'Node {versioned_ref.id} is still used by relations '
                           f'{",".join(str(ref.id) for ref in ref_relations)}.')
            else:
                raise NotImplementedError(f'Unsupported element type {next(iter(used_by)).type!r}')
        elif versioned_ref.type == ElementType.way:
            if ref_relations := tuple(ref for ref in used_by if ref.type == ElementType.relation):
                raise cls.APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'Way {versioned_ref.id} is still used by relations '
                           f'{",".join(str(ref.id) for ref in ref_relations)}.')
            else:
                raise NotImplementedError(f'Unsupported element type {next(iter(used_by)).type!r}')
        elif versioned_ref.type == ElementType.relation:
            if ref_relations := tuple(ref for ref in used_by if ref.type == ElementType.relation):
                raise cls.APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'The relation {versioned_ref.id} is used in relation '
                           f'{ref_relations[0].id}.')
            else:
                raise NotImplementedError(f'Unsupported element type {next(iter(used_by)).type!r}')
        else:
            raise NotImplementedError(f'Unsupported element type {versioned_ref.type!r}')

    @classmethod
    def raise_for_diff_unsupported_action(cls, action: str) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Unknown action {action}, choices are create, modify, delete')

    @classmethod
    def raise_for_diff_create_bad_id(cls, versioned_ref: VersionedElementRef) -> NoReturn:
        if versioned_ref.type == ElementType.node:
            raise cls.APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail=f'Cannot create node: data is invalid.')
        elif versioned_ref.type == ElementType.way:
            raise cls.APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail=f'Cannot create way: data is invalid.')
        elif versioned_ref.type == ElementType.relation:
            raise cls.APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail=f'Cannot create relation: data or member data is invalid.')
        else:
            raise NotImplementedError(f'Unsupported element type {versioned_ref.type.type!r}')

    @classmethod
    def raise_for_diff_update_bad_version(cls, versioned_ref: VersionedElementRef) -> NoReturn:
        raise cls.APIError(
            status.HTTP_412_PRECONDITION_FAILED,
            detail=f'Update action requires version >= 1, got {versioned_ref.version - 1}')

    @classmethod
    def raise_for_element_redacted(cls, versioned_ref: VersionedElementRef) -> NoReturn:
        # TODO: 0.7 legal reasons
        return cls.raise_for_element_not_found(versioned_ref)

    @classmethod
    def raise_for_redact_latest_version(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Cannot redact current version of element, only historical versions may be redacted')

    @classmethod
    def raise_for_oauth1_timestamp_out_of_range(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'OAuth timestamp out of range')

    @classmethod
    def raise_for_oauth1_nonce_missing(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'OAuth nonce missing')

    @classmethod
    def raise_for_oauth1_bad_nonce(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'OAuth nonce invalid')

    @classmethod
    def raise_for_oauth1_nonce_used(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail=f'OAuth nonce already used')

    @classmethod
    def raise_for_oauth1_bad_verifier(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail=f'OAuth verifier invalid')

    @classmethod
    def raise_for_oauth1_unsupported_signature_method(cls, method: str) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'OAuth unsupported signature method {method!r}')

    @classmethod
    def raise_for_oauth1_bad_signature(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail=f'OAuth signature invalid')

    @classmethod
    def raise_for_oauth2_bearer_missing(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail=f'OAuth2 bearer authorization header missing')

    @classmethod
    def raise_for_oauth2_challenge_method_not_set(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'OAuth2 verifier provided but code challenge method is not set')

    @classmethod
    def raise_for_oauth2_bad_verifier(cls, code_challenge_method: OAuth2CodeChallengeMethod) -> NoReturn:
        return cls.APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail=f'OAuth2 verifier invalid for {code_challenge_method.value} code challenge method')

    @classmethod
    def raise_for_oauth_bad_app_token(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail=f'OAuth application token invalid')

    @classmethod
    def raise_for_oauth_bad_user_token(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail=f'OAuth user token invalid')

    @classmethod
    def raise_for_oauth_bad_redirect_uri(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'OAuth redirect uri invalid')

    @classmethod
    def raise_for_oauth_bad_scopes(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'OAuth scopes invalid')

    @classmethod
    def raise_for_map_query_area_too_big(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'The maximum bbox size is {MAP_QUERY_AREA_MAX_SIZE}, and your request was too large. Either request a smaller area, or use planet.osm')

    @classmethod
    def raise_for_map_query_nodes_limit_exceeded(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'You requested too many nodes (limit is {MAP_QUERY_LEGACY_NODES_LIMIT}). Either request a smaller area, or use planet.osm')

    @classmethod
    def raise_for_notes_query_area_too_big(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'The maximum bbox size is {NOTE_QUERY_AREA_MAX_SIZE}, and your request was too large. Please request a smaller area.')

    @classmethod
    def raise_for_trace_points_query_area_too_big(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'The maximum bbox size is {TRACE_POINT_QUERY_AREA_MAX_SIZE}, and your request was too large. Please request a smaller area.')

    @classmethod
    def raise_for_trace_file_unsupported_format(cls, format: str) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Unsupported trace file format {format!r}')

    @classmethod
    def raise_for_trace_file_archive_too_deep(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f'Trace file archive is too deep')

    @classmethod
    def raise_for_trace_file_archive_corrupted(cls, format: str) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Trace file archive failed to decompress {format!r}')

    @classmethod
    def raise_for_trace_file_archive_too_many_files(cls) -> NoReturn:
        return cls.APIError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f'Trace file archive contains too many files')

    @classmethod
    def raise_for_bad_trace_file(cls, message: str) -> NoReturn:
        return cls.APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Failed to parse trace file: {message}')

    @classmethod
    def raise_for_note_closed(cls, note_id: SequentialId, closed_at: datetime) -> NoReturn:
        return cls.APIError(
            status.HTTP_409_CONFLICT,
            detail=f'The note {note_id} was closed at {format_iso_date(closed_at)}')

    @classmethod
    def raise_for_note_open(cls, note_id: SequentialId) -> NoReturn:
        return cls.APIError(
            status.HTTP_409_CONFLICT,
            detail=f'The note {note_id} is already open')
