from abc import abstractmethod
from collections.abc import Sequence
from typing import NoReturn

from fastapi import status

from app.exceptions.api_error import APIError
from app.models.typed_element_ref import TypedElementRef
from app.models.versioned_element_ref import VersionedElementRef


class ElementExceptionsMixin:
    @abstractmethod
    def element_not_found(self, element_ref: VersionedElementRef | TypedElementRef) -> NoReturn:
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
    def element_member_not_found(self, initiator_ref: VersionedElementRef, member_ref: TypedElementRef) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def element_in_use(self, versioned_ref: VersionedElementRef, used_by: Sequence[TypedElementRef]) -> NoReturn:
        raise NotImplementedError
