"""Default Exceptions implementation — used for non-API-0.6 paths.

Methods raising ``NotImplementedError`` are API-0.6-only and have concrete
overrides in :class:`app.exceptions.api06.Exceptions06`. They should not be
called from the default-routed code paths.
"""

from collections.abc import Iterable
from datetime import datetime
from typing import TYPE_CHECKING, NoReturn

from starlette import status

from app.config import TRACE_POINT_QUERY_AREA_MAX_SIZE
from app.exceptions.api_error import APIError
from app.models.element import TypedElementId
from app.models.types import (
    ApplicationId,
    ChangesetCommentId,
    ChangesetId,
    DiaryCommentId,
    DiaryId,
    DisplayName,
    MessageId,
    NoteId,
    TraceId,
    UserId,
    UserPrefKey,
)
from speedup import element_type

if TYPE_CHECKING:
    from app.models.db.element import Element, ElementInit
    from app.models.db.oauth2_token import OAuth2CodeChallengeMethod


class Exceptions:
    # --- auth ---
    def unauthorized(self, *, request_basic_auth: bool = False):
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            detail='Unauthorized',
            headers=(
                {'WWW-Authenticate': 'Basic realm="Access to OpenStreetMap"'}
                if request_basic_auth
                else None
            ),
        )

    def insufficient_scopes(self, scopes: Iterable[str]) -> NoReturn:
        required_scopes = ' '.join(sorted(set(scopes)))
        raise APIError(
            status.HTTP_403_FORBIDDEN,
            detail=f'insufficient_scope: scope="{required_scopes}"',
        )

    def bad_user_token_struct(self):
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='invalid_token')

    def bad_basic_auth_format(self) -> NoReturn:
        raise NotImplementedError

    def oauth2_bearer_missing(self) -> NoReturn:
        raise NotImplementedError

    def oauth2_bad_code_challenge_params(self):
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='invalid_code_challenge')

    def oauth2_challenge_method_not_set(self):
        raise APIError(
            status.HTTP_400_BAD_REQUEST, detail='invalid_code_challenge_method'
        )

    def oauth2_bad_verifier(
        self, code_challenge_method: OAuth2CodeChallengeMethod
    ) -> NoReturn:
        raise NotImplementedError

    def oauth_bad_client_id(self):
        raise APIError(status.HTTP_401_UNAUTHORIZED, detail='invalid_client')

    def oauth_bad_client_secret(self):
        raise APIError(status.HTTP_401_UNAUTHORIZED, detail='invalid_client')

    def oauth_bad_user_token(self):
        raise APIError(status.HTTP_401_UNAUTHORIZED, detail='invalid_token')

    def oauth_bad_redirect_uri(self):
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='invalid_redirect_uri')

    def oauth_bad_scopes(self):
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='invalid_scope')

    # --- changeset ---
    def changeset_not_found(self, changeset_id: ChangesetId):
        raise APIError(status.HTTP_404_NOT_FOUND, detail='Changeset not found')

    def changeset_access_denied(self) -> NoReturn:
        raise NotImplementedError

    def changeset_already_closed(
        self, changeset_id: ChangesetId, closed_at: datetime
    ) -> NoReturn:
        raise NotImplementedError

    def changeset_not_subscribed(self, changeset_id: ChangesetId) -> NoReturn:
        raise NotImplementedError

    def changeset_already_subscribed(self, changeset_id: ChangesetId) -> NoReturn:
        raise NotImplementedError

    def changeset_too_big(self, size: int) -> NoReturn:
        raise NotImplementedError

    def changeset_comment_not_found(self, comment_id: ChangesetCommentId) -> NoReturn:
        raise NotImplementedError

    # --- diary ---
    def diary_not_found(self, id: DiaryId):
        raise APIError(status.HTTP_404_NOT_FOUND, detail='Diary not found')

    def diary_comment_not_found(self, id: DiaryCommentId):
        raise APIError(status.HTTP_404_NOT_FOUND, detail='Diary comment not found')

    # --- diff ---
    def diff_multiple_changesets(self) -> NoReturn:
        raise NotImplementedError

    def diff_unsupported_action(self, action: str) -> NoReturn:
        raise NotImplementedError

    def diff_create_bad_id(self, element: ElementInit) -> NoReturn:
        raise NotImplementedError

    def diff_update_bad_version(self, element: ElementInit) -> NoReturn:
        raise NotImplementedError

    def diff_null_island(self, count: int) -> NoReturn:
        raise NotImplementedError

    # --- element ---
    def element_not_found(
        self, element_ref: TypedElementId | tuple[TypedElementId, int]
    ):
        if isinstance(element_ref, int):
            type = element_type(element_ref)
            raise APIError(
                status.HTTP_404_NOT_FOUND,
                detail=f'{type.title()} not found',
            )
        else:
            type = element_type(element_ref[0])
            raise APIError(
                status.HTTP_404_NOT_FOUND,
                detail=f'{type.title()} version not found',
            )

    def element_redacted(self, versioned_ref: tuple[TypedElementId, int]):
        type = element_type(versioned_ref[0])
        raise APIError(
            status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS,
            detail=f'{type.title()} version is redacted',
        )

    def element_redact_latest(self) -> NoReturn:
        raise NotImplementedError

    def element_already_deleted(self, element_ref: TypedElementId) -> NoReturn:
        raise NotImplementedError

    def element_changeset_missing(self) -> NoReturn:
        raise NotImplementedError

    def element_version_conflict(
        self, element: Element | ElementInit, local_version: int
    ) -> NoReturn:
        raise NotImplementedError

    def element_member_not_found(
        self, parent_ref: TypedElementId, member_ref: TypedElementId
    ) -> NoReturn:
        raise NotImplementedError

    def element_in_use(
        self, element_ref: TypedElementId, used_by: list[TypedElementId]
    ) -> NoReturn:
        raise NotImplementedError

    # --- image ---
    def image_not_found(self):
        raise APIError(status.HTTP_404_NOT_FOUND, detail='Image not found')

    def image_too_big(self):
        raise APIError(status.HTTP_413_CONTENT_TOO_LARGE, detail='Image is too large')

    def image_inappropriate(self):
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='Image violates content policy',
        )

    # --- map ---
    def map_query_area_too_big(self) -> NoReturn:
        raise NotImplementedError

    def map_query_nodes_limit_exceeded(self):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='Requested map data is too large',
        )

    # --- message ---
    def message_not_found(self, message_id: MessageId):
        raise APIError(status.HTTP_404_NOT_FOUND, detail='Message not found')

    # --- note ---
    def note_not_found(self, note_id: NoteId):
        raise APIError(status.HTTP_404_NOT_FOUND, detail='Note not found')

    def note_closed(self, note_id: NoteId, closed_at: datetime) -> NoReturn:
        raise NotImplementedError

    def note_open(self, note_id: NoteId) -> NoReturn:
        raise NotImplementedError

    def note_null_island(self) -> NoReturn:
        raise NotImplementedError

    def notes_query_area_too_big(self) -> NoReturn:
        raise NotImplementedError

    # --- request ---
    def request_timeout(self):
        raise APIError(status.HTTP_504_GATEWAY_TIMEOUT, detail='Request timed out')

    def too_many_requests(self):
        raise APIError(status.HTTP_429_TOO_MANY_REQUESTS, detail='Too many requests')

    def bad_cursor(self):
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='Invalid database cursor')

    def cursor_expired(self):
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='Database cursor expired')

    def bad_geometry(self) -> NoReturn:
        raise NotImplementedError

    def bad_geometry_coordinates(self) -> NoReturn:
        raise NotImplementedError

    def bad_bbox(self, bbox: str, condition: str | None = None) -> NoReturn:
        raise NotImplementedError

    def bad_xml(
        self, name: str, message: str, xml_input: bytes | None = None
    ) -> NoReturn:
        raise NotImplementedError

    def input_too_big(self, size: int) -> NoReturn:
        raise NotImplementedError

    # --- trace ---
    def trace_not_found(self, trace_id: TraceId):
        raise APIError(status.HTTP_404_NOT_FOUND, detail='Trace not found')

    def trace_access_denied(self, trace_id: TraceId):
        raise APIError(status.HTTP_403_FORBIDDEN, detail='Trace access denied')

    def trace_points_query_area_too_big(self):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Trace query area is too large (maximum {TRACE_POINT_QUERY_AREA_MAX_SIZE})',
        )

    def trace_file_unsupported_format(self, content_type: str):
        raise APIError(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f'Trace file format is not supported: {content_type!r}',
        )

    def trace_file_archive_too_deep(self):
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='Trace file archive is too deep',
        )

    def trace_file_archive_corrupted(self, content_type: str):
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f'Trace file archive is corrupted: {content_type!r}',
        )

    def trace_file_archive_too_many_files(self):
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='Trace file archive contains too many files',
        )

    def bad_trace_file(self, message: str):
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f'Trace file is invalid: {message}',
        )

    # --- user ---
    def user_not_found(self, name_or_id: DisplayName | UserId):
        raise APIError(status.HTTP_404_NOT_FOUND, detail='User not found')

    def user_not_found_bad_request(self, name_or_id: DisplayName | UserId) -> NoReturn:
        raise NotImplementedError

    def pref_not_found(
        self, app_id: ApplicationId | None, key: UserPrefKey
    ) -> NoReturn:
        raise NotImplementedError

    def pref_duplicate_key(self, key: UserPrefKey) -> NoReturn:
        raise NotImplementedError

    def pref_bulk_set_limit_exceeded(self) -> NoReturn:
        raise NotImplementedError
