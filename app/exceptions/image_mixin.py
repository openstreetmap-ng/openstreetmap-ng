from abc import abstractmethod
from typing import NoReturn


class ImageExceptionsMixin:
    @abstractmethod
    def image_not_found(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def image_too_big(self) -> NoReturn:
        raise NotImplementedError
