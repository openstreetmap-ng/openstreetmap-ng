from typing import NoReturn, override

from fastapi import status

from app.exceptions import APIError
from app.exceptions.diff_mixin import DiffExceptionsMixin
from app.models.element_type import ElementType
from app.models.versioned_element_ref import VersionedElementRef


class DiffExceptions06Mixin(DiffExceptionsMixin):
    @override
    def diff_multiple_changesets(self) -> NoReturn:
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='Only one changeset can be modified at a time')

    @override
    def diff_unsupported_action(self, action: str) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Unknown action {action}, choices are create, modify, delete',
        )

    @override
    def diff_create_bad_id(self, versioned_ref: VersionedElementRef) -> NoReturn:
        if versioned_ref.type == ElementType.node:
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail='Cannot create node: data is invalid.',
            )
        elif versioned_ref.type == ElementType.way:
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail='Cannot create way: data is invalid.',
            )
        elif versioned_ref.type == ElementType.relation:
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail='Cannot create relation: data or member data is invalid.',
            )
        else:
            raise NotImplementedError(f'Unsupported element type {versioned_ref.type.type!r}')

    @override
    def diff_update_bad_version(self, versioned_ref: VersionedElementRef) -> NoReturn:
        raise APIError(
            status.HTTP_412_PRECONDITION_FAILED,
            detail=f'Update action requires version >= 1, got {versioned_ref.version - 1}',
        )
