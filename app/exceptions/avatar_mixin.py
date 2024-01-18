from abc import abstractmethod
from typing import NoReturn


class AvatarExceptionsMixin:
    @abstractmethod
    def avatar_not_found(self, avatar_id: str) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def avatar_too_big(self) -> NoReturn:
        raise NotImplementedError
