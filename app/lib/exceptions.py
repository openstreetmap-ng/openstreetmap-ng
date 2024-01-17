from abc import abstractmethod
from collections.abc import Sequence
from datetime import datetime
from typing import NoReturn

from fastapi import HTTPException, status

from app.models.oauth2_code_challenge_method import OAuth2CodeChallengeMethod
from app.models.typed_element_ref import TypedElementRef
from app.models.versioned_element_ref import VersionedElementRef


class APIError(HTTPException):
    pass


# TODO: mixin
# TODO: finish implementing
class Exceptions:
    def request_uri_too_long(self) -> NoReturn:
        raise APIError(
            status.HTTP_414_REQUEST_URI_TOO_LONG,
            detail='URI Too Long',
        )

    def request_timeout(self) -> NoReturn:
        raise APIError(
            status.HTTP_504_GATEWAY_TIMEOUT,
            detail='Request timed out',
        )

    def rate_limit(self) -> NoReturn:
        raise APIError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail='Too many requests',
        )

    def time_integrity(self) -> NoReturn:
        raise APIError(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Time integrity error',
        )

    def bad_cursor(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='Invalid database cursor',
        )

    def cursor_expired(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='Database cursor expired',
        )

    def bad_user_token_struct(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='Invalid user token',
        )

    @abstractmethod
    def unauthorized(self, *, request_basic_auth: bool = False) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def insufficient_scopes(self, scopes: Sequence[str]) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def bad_basic_auth_format(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def bad_geometry(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def bad_geometry_coordinates(self, lon: float, lat: float) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def bad_bbox(self, bbox: str, condition: str | None = None) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def bad_xml(self, name: str, message: str, xml_input: str) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def input_too_big(self, size: int) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def avatar_not_found(self, avatar_id: str) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def avatar_too_big(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def user_not_found(self, name_or_id: str | int) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def user_not_found_bad_request(self, name_or_id: str | int) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def changeset_not_found(self, changeset_id: int) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def changeset_access_denied(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def changeset_not_closed(self, changeset_id: int) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def changeset_already_closed(self, changeset_id: int, closed_at: datetime) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def changeset_not_subscribed(self, changeset_id: int) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def changeset_already_subscribed(self, changeset_id: int) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def changeset_too_big(self, size: int) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def changeset_comment_not_found(self, comment_id: int) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def element_not_found(self, element_ref: VersionedElementRef | TypedElementRef) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def element_already_deleted(self, versioned_ref: VersionedElementRef) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def element_changeset_missing(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def element_version_conflict(self, versioned_ref: VersionedElementRef, local_version: int) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def element_member_not_found(self, initiator_ref: VersionedElementRef, member_ref: TypedElementRef) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def element_in_use(self, versioned_ref: VersionedElementRef, used_by: Sequence[TypedElementRef]) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def diff_multiple_changesets(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def diff_unsupported_action(self, action: str) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def diff_create_bad_id(self, versioned_ref: VersionedElementRef) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def diff_update_bad_version(self, versioned_ref: VersionedElementRef) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def element_redacted(self, versioned_ref: VersionedElementRef) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def redact_latest_version(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def oauth1_timestamp_out_of_range(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def oauth1_nonce_missing(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def oauth1_bad_nonce(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def oauth1_nonce_used(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def oauth1_bad_verifier(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def oauth1_unsupported_signature_method(self, method: str) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def oauth1_bad_signature(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def oauth2_bearer_missing(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def oauth2_challenge_method_not_set(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def oauth2_bad_verifier(self, code_challenge_method: OAuth2CodeChallengeMethod) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def oauth_bad_app_token(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def oauth_bad_user_token(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def oauth_bad_redirect_uri(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def oauth_bad_scopes(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def map_query_area_too_big(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def map_query_nodes_limit_exceeded(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def notes_query_area_too_big(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def trace_not_found(self, trace_id: int) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def trace_access_denied(self, trace_id: int) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def trace_points_query_area_too_big(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def trace_file_unsupported_format(self, content_type: str) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def trace_file_archive_too_deep(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def trace_file_archive_corrupted(self, content_type: str) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def trace_file_archive_too_many_files(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def bad_trace_file(self, message: str) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def note_not_found(self, note_id: int) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def note_closed(self, note_id: int, closed_at: datetime) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def note_open(self, note_id: int) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def pref_not_found(self, app_id: int | None, key: str) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def pref_duplicate_key(self, key: str) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def pref_bulk_set_limit_exceeded(self) -> NoReturn:
        raise NotImplementedError
