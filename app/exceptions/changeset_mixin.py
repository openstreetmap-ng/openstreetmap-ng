from abc import abstractmethod
from datetime import datetime
from typing import NoReturn

from app.models.db.changeset import ChangesetId
from app.models.db.changeset_comment import ChangesetCommentId


class ChangesetExceptionsMixin:
    @abstractmethod
    def changeset_not_found(self, changeset_id: ChangesetId) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def changeset_access_denied(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def changeset_already_closed(self, changeset_id: ChangesetId, closed_at: datetime) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def changeset_not_subscribed(self, changeset_id: ChangesetId) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def changeset_already_subscribed(self, changeset_id: ChangesetId) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def changeset_too_big(self, size: int) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def changeset_comment_not_found(self, comment_id: ChangesetCommentId) -> NoReturn:
        raise NotImplementedError
