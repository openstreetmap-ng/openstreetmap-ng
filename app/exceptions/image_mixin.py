from abc import abstractmethod
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from app.lib.storage.base import StorageKey


class ImageExceptionsMixin:
    @abstractmethod
    def image_not_found(self, file_id: 'StorageKey') -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def image_too_big(self) -> NoReturn:
        raise NotImplementedError
