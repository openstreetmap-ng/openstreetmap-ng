from abc import abstractmethod
from typing import TYPE_CHECKING, NoReturn

from starlette import status

from app.exceptions.api_error import APIError
from app.models.element import TypedElementId
from speedup import split_typed_element_id

if TYPE_CHECKING:
    from app.models.db.element import Element, ElementInit


class ElementExceptionsMixin:
    def element_not_found(
        self, element_ref: TypedElementId | tuple[TypedElementId, int]
    ) -> NoReturn:
        if isinstance(element_ref, int):
            type, id = split_typed_element_id(element_ref)
            # version = None
        else:
            type, id = split_typed_element_id(element_ref[0])
            # version = element_ref[1]

        raise APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'{type}/{id} not found',
        )

    def element_redacted(self, versioned_ref: tuple[TypedElementId, int]) -> NoReturn:
        type, id = split_typed_element_id(versioned_ref[0])
        version = versioned_ref[1]
        raise APIError(
            status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS,
            detail=f'{type}/{id}v{version} redacted',
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
