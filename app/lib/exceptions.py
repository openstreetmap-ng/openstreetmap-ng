from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from typing import NoReturn

from fastapi import HTTPException, status

from app.models.oauth2_code_challenge_method import OAuth2CodeChallengeMethod
from app.models.typed_element_ref import TypedElementRef
from app.models.versioned_element_ref import VersionedElementRef


# TODO: new implementation
class Exceptions:
    class APIError(HTTPException):
        pass

    @classmethod
    def request_uri_too_long(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_414_REQUEST_URI_TOO_LONG, detail='URI Too Long')

    @classmethod
    def request_timeout(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_504_GATEWAY_TIMEOUT, detail='Request timed out')

    @classmethod
    def rate_limit(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_429_TOO_MANY_REQUESTS, detail='Too many requests')

    @classmethod
    def time_integrity(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Time integrity error')

    @classmethod
    def bad_cursor(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_400_BAD_REQUEST, detail='Invalid database cursor')

    @classmethod
    def cursor_expired(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_400_BAD_REQUEST, detail='Database cursor expired')

    @classmethod
    def bad_user_token_struct(cls) -> NoReturn:
        raise cls.APIError(status.HTTP_400_BAD_REQUEST, detail='Invalid user token')

    @classmethod
    @abstractmethod
    def unauthorized(cls, *, request_basic_auth: bool = False) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def insufficient_scopes(cls, scopes: Sequence[str]) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def bad_basic_auth_format(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def bad_geometry(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def bad_geometry_coordinates(cls, lon: float, lat: float) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def bad_bbox(cls, bbox: str, condition: str | None = None) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def bad_xml(cls, name: str, message: str, xml_input: str) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def input_too_big(cls, size: int) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def avatar_not_found(cls, avatar_id: str) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def avatar_too_big(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def user_not_found(cls, name_or_id: str | int) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def user_not_found_bad_request(cls, name_or_id: str | int) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def changeset_not_found(cls, changeset_id: int) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def changeset_access_denied(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def changeset_not_closed(cls, changeset_id: int) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def changeset_already_closed(cls, changeset_id: int, closed_at: datetime) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def changeset_not_subscribed(cls, changeset_id: int) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def changeset_already_subscribed(cls, changeset_id: int) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def changeset_too_big(cls, size: int) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def changeset_comment_not_found(cls, comment_id: int) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def element_not_found(cls, element_ref: VersionedElementRef | TypedElementRef) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def element_already_deleted(cls, versioned_ref: VersionedElementRef) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def element_changeset_missing(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def element_version_conflict(cls, versioned_ref: VersionedElementRef, local_version: int) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def element_member_not_found(cls, initiator_ref: VersionedElementRef, member_ref: TypedElementRef) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def element_in_use(cls, versioned_ref: VersionedElementRef, used_by: Sequence[TypedElementRef]) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def diff_multiple_changesets(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def diff_unsupported_action(cls, action: str) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def diff_create_bad_id(cls, versioned_ref: VersionedElementRef) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def diff_update_bad_version(cls, versioned_ref: VersionedElementRef) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def element_redacted(cls, versioned_ref: VersionedElementRef) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def redact_latest_version(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def oauth1_timestamp_out_of_range(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def oauth1_nonce_missing(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def oauth1_bad_nonce(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def oauth1_nonce_used(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def oauth1_bad_verifier(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def oauth1_unsupported_signature_method(cls, method: str) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def oauth1_bad_signature(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def oauth2_bearer_missing(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def oauth2_challenge_method_not_set(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def oauth2_bad_verifier(cls, code_challenge_method: OAuth2CodeChallengeMethod) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def oauth_bad_app_token(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def oauth_bad_user_token(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def oauth_bad_redirect_uri(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def oauth_bad_scopes(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def map_query_area_too_big(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def map_query_nodes_limit_exceeded(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def notes_query_area_too_big(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def trace_not_found(cls, trace_id: int) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def trace_access_denied(cls, trace_id: int) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def trace_points_query_area_too_big(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def trace_file_unsupported_format(cls, content_type: str) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def trace_file_archive_too_deep(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def trace_file_archive_corrupted(cls, content_type: str) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def trace_file_archive_too_many_files(cls) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def bad_trace_file(cls, message: str) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def note_not_found(cls, note_id: int) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def note_closed(cls, note_id: int, closed_at: datetime) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def note_open(cls, note_id: int) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def pref_not_found(cls, app_id: int | None, key: str) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def pref_duplicate_key(cls, key: str) -> NoReturn:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def pref_bulk_set_limit_exceeded(cls) -> NoReturn:
        raise NotImplementedError
