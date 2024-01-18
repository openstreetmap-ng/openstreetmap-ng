from abc import abstractmethod
from datetime import datetime
from typing import NoReturn


class ChangesetExceptionsMixin:
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
