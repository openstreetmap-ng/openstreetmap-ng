from abc import ABC, abstractclassmethod
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from typing import NoReturn, Sequence, Type

from fastapi import HTTPException

from models.collections.base_sequential import SequentialId
from models.oauth2_code_challenge_method import OAuth2CodeChallengeMethod
from models.typed_element_ref import TypedElementRef
from models.versioned_element_ref import VersionedElementRef


class Exceptions(ABC):
    _context = ContextVar('Exceptions_context')

    @classmethod
    @contextmanager
    def exceptions_context(cls, exceptions_type: Type['ExceptionsBase']):
        '''
        Context manager for setting the exceptions type in ContextVar.
        '''
        token = cls._context.set(exceptions_type)
        try:
            yield
        finally:
            cls._context.reset(token)

    @classmethod
    def get(cls) -> Type['ExceptionsBase']:
        '''
        Get the exceptions type from ContextVar.

        Return a type of a subclass of `ExceptionsBase`.
        '''
        return cls._context.get()


class ExceptionsBase(ABC):
    class APIError(HTTPException):
        pass

    @abstractclassmethod
    def raise_for_timeout(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_rate_limit(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_time_integrity(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_bad_cursor(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_cursor_expired(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_unauthorized(cls, *, request_basic_auth: bool = False) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_insufficient_scopes(cls, scopes: Sequence[str]) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_bad_basic_auth_format(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_bad_geometry(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_bad_geometry_coordinates(cls, lon: float, lat: float) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_bad_bbox(cls, bbox: str, condition: str | None = None) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_bad_xml(cls, name: str, message: str, input: str) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_input_too_big(cls, size: int) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_user_not_found(cls, name_or_id: str | SequentialId) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_changeset_not_found(cls, changeset_id: SequentialId) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_changeset_access_denied(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_changeset_not_closed(cls, changeset_id: SequentialId) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_changeset_already_closed(cls, changeset_id: SequentialId, closed_at: datetime) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_changeset_not_subscribed(cls, changeset_id: SequentialId) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_changeset_already_subscribed(cls, changeset_id: SequentialId) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_changeset_too_big(cls, size: int) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_changeset_comment_not_found(cls, comment_id: SequentialId) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_element_not_found(cls, element_ref: VersionedElementRef | TypedElementRef) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_element_already_deleted(cls, versioned_ref: VersionedElementRef) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_element_changeset_missing(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_element_version_conflict(cls, versioned_ref: VersionedElementRef, local_version: int) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_element_member_not_found(cls, initiator_ref: VersionedElementRef, member_ref: TypedElementRef) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_element_in_use(cls, versioned_ref: VersionedElementRef, used_by: Sequence[TypedElementRef]) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_diff_unsupported_action(cls, action: str) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_diff_create_bad_id(cls, versioned_ref: VersionedElementRef) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_diff_update_bad_version(cls, versioned_ref: VersionedElementRef) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_element_redacted(cls, versioned_ref: VersionedElementRef) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_redact_latest_version(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_oauth1_timestamp_out_of_range(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_oauth1_nonce_missing(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_oauth1_bad_nonce(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_oauth1_nonce_used(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_oauth1_bad_verifier(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_oauth1_unsupported_signature_method(cls, method: str) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_oauth1_bad_signature(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_oauth2_bearer_missing(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_oauth2_challenge_method_not_set(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_oauth2_bad_verifier(cls, code_challenge_method: OAuth2CodeChallengeMethod) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_oauth_bad_app_token(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_oauth_bad_user_token(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_oauth_bad_redirect_uri(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_oauth_bad_scopes(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_map_query_area_too_big(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_map_query_nodes_limit_exceeded(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_notes_query_area_too_big(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_trace_points_query_area_too_big(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_trace_file_unsupported_format(cls, format: str) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_trace_file_archive_too_deep(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_trace_file_archive_corrupted(cls, format: str) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_trace_file_archive_too_many_files(cls) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_bad_trace_file(cls, message: str) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_note_closed(cls, note_id: SequentialId, closed_at: datetime) -> NoReturn:
        raise NotImplementedError

    @abstractclassmethod
    def raise_for_note_open(cls, note_id: SequentialId) -> NoReturn:
        raise NotImplementedError
