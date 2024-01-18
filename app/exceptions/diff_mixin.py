from abc import abstractmethod
from typing import NoReturn

from app.models.versioned_element_ref import VersionedElementRef


class DiffExceptionsMixin:
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
