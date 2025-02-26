from abc import abstractmethod
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from app.models.db.element import ElementInit


class DiffExceptionsMixin:
    @abstractmethod
    def diff_multiple_changesets(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def diff_unsupported_action(self, action: str) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def diff_create_bad_id(self, element: 'ElementInit') -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def diff_update_bad_version(self, element: 'ElementInit') -> NoReturn:
        raise NotImplementedError
