from abc import abstractmethod
from typing import NoReturn


class MapExceptionsMixin:
    @abstractmethod
    def map_query_area_too_big(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def map_query_nodes_limit_exceeded(self) -> NoReturn:
        raise NotImplementedError
