from abc import abstractmethod
from typing import NoReturn


class BackgroundExceptionsMixin:
    @abstractmethod
    def background_not_found(self, background_id: str) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def background_too_big(self) -> NoReturn:
        raise NotImplementedError
