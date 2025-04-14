from abc import abstractmethod
from typing import TYPE_CHECKING, NoReturn

from starlette import status

from app.exceptions.api_error import APIError
from app.models.element import TypedElementId

if TYPE_CHECKING:
    from app.models.db.element import Element, ElementInit


class ElementExceptionsMixin:
    @abstractmethod
    def element_not_found(
        self, element_ref: TypedElementId | tuple[TypedElementId, int]
    ) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def element_redacted(self, versioned_ref: tuple[TypedElementId, int]) -> NoReturn:
        raise APIError(
            status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS,
            detail='Element version redacted',
        )

    @abstractmethod
    def element_redact_latest(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def element_already_deleted(self, element_ref: TypedElementId) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def element_changeset_missing(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def element_version_conflict(
        self, element: 'Element | ElementInit', local_version: int
    ) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def element_member_not_found(
        self, parent_ref: TypedElementId, member_ref: TypedElementId
    ) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def element_in_use(
        self, element_ref: TypedElementId, used_by: list[TypedElementId]
    ) -> NoReturn:
        raise NotImplementedError
