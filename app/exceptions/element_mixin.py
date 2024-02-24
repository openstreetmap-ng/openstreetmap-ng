from abc import abstractmethod
from collections.abc import Sequence
from typing import NoReturn

from starlette import status

from app.exceptions.api_error import APIError
from app.models.element_ref import ElementRef
from app.models.versioned_element_ref import VersionedElementRef


class ElementExceptionsMixin:
    @abstractmethod
    def element_not_found(self, element_ref: VersionedElementRef | ElementRef) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def element_redacted(self, versioned_ref: VersionedElementRef) -> NoReturn:
        raise APIError(status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS, detail='Element version redacted')

    @abstractmethod
    def element_redact_latest(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def element_already_deleted(self, versioned_ref: VersionedElementRef) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def element_changeset_missing(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def element_version_conflict(self, versioned_ref: VersionedElementRef, local_version: int) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def element_member_not_found(self, initiator_ref: VersionedElementRef, member_ref: ElementRef) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def element_in_use(self, versioned_ref: VersionedElementRef, used_by: Sequence[ElementRef]) -> NoReturn:
        raise NotImplementedError
