from datetime import datetime
from typing import NoReturn, override

from starlette import status

from app.exceptions.api_error import APIError
from app.exceptions.changeset_mixin import ChangesetExceptionsMixin
from app.lib.date_utils import legacy_date
from app.models.db.changeset import ChangesetId
from app.models.db.changeset_comment import ChangesetCommentId


class ChangesetExceptions06Mixin(ChangesetExceptionsMixin):
    @override
    def changeset_not_found(self, changeset_id: ChangesetId) -> NoReturn:
        raise APIError(status.HTTP_404_NOT_FOUND, detail=f'The changeset with the id {changeset_id} was not found')

    @override
    def changeset_access_denied(self) -> NoReturn:
        raise APIError(status.HTTP_409_CONFLICT, detail="The user doesn't own that changeset")

    @override
    def changeset_already_closed(self, changeset_id: ChangesetId, closed_at: datetime) -> NoReturn:
        raise APIError(
            status.HTTP_409_CONFLICT,
            detail=f'The changeset {changeset_id} was closed at {legacy_date(closed_at).isoformat()}',
        )

    @override
    def changeset_not_subscribed(self, changeset_id: ChangesetId) -> NoReturn:
        raise APIError(status.HTTP_404_NOT_FOUND, detail=f'You are not subscribed to changeset {changeset_id}.')

    @override
    def changeset_already_subscribed(self, changeset_id: ChangesetId) -> NoReturn:
        raise APIError(status.HTTP_409_CONFLICT, detail=f'The user is already subscribed to changeset {changeset_id}')

    @override
    def changeset_too_big(self, size: int) -> NoReturn:
        raise APIError(
            status.HTTP_412_PRECONDITION_FAILED,
            detail=f'Changeset size {size} is too big. Please split your changes into multiple changesets.',
        )

    @override
    def changeset_comment_not_found(self, comment_id: ChangesetCommentId) -> NoReturn:
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'The changeset comment with the id {comment_id} was not found',
        )
