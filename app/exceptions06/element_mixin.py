from collections.abc import Sequence
from typing import NoReturn, override

from fastapi import status

from app.exceptions.api_error import APIError
from app.exceptions.element_mixin import ElementExceptionsMixin
from app.models.element_ref import ElementRef
from app.models.element_type import ElementType
from app.models.versioned_element_ref import VersionedElementRef


class ElementExceptions06Mixin(ElementExceptionsMixin):
    @override
    def element_not_found(self, element_ref: VersionedElementRef | ElementRef) -> NoReturn:
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'The {element_ref.type} with the id {element_ref.id} was not found',
        )

    @override
    def element_redacted(self, versioned_ref: VersionedElementRef) -> NoReturn:
        return self.element_not_found(versioned_ref)

    @override
    def element_redact_latest(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='Cannot redact current version of element, only historical versions may be redacted',
        )

    @override
    def element_already_deleted(self, versioned_ref: VersionedElementRef) -> NoReturn:
        raise APIError(
            status.HTTP_412_PRECONDITION_FAILED,
            detail=f'Cannot delete an already deleted {versioned_ref.type} with id {versioned_ref.id}.',
        )

    @override
    def element_changeset_missing(self) -> NoReturn:
        raise APIError(status.HTTP_409_CONFLICT, detail='You need to supply a changeset to be able to make a change')

    @override
    def element_version_conflict(self, versioned_ref: VersionedElementRef, local_version: int) -> NoReturn:
        raise APIError(
            status.HTTP_409_CONFLICT,
            detail=f'Version mismatch: Provided {versioned_ref.version - 1}, server had: {local_version} of {versioned_ref.type} {versioned_ref.id}',
        )

    @override
    def element_member_not_found(self, initiator_ref: VersionedElementRef, member_ref: ElementRef) -> NoReturn:
        if initiator_ref.type == ElementType.way:
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail=f'Way {initiator_ref.id} requires the nodes with id in ({member_ref.id}), which either do not exist, or are not visible.',
            )
        elif initiator_ref.type == ElementType.relation:
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail=f'Relation with id {initiator_ref.id} cannot be saved due to {member_ref.type} with id {member_ref.id}',
            )
        else:
            raise NotImplementedError(f'Unsupported element type {initiator_ref.type!r}')

    @override
    def element_in_use(self, versioned_ref: VersionedElementRef, used_by: Sequence[ElementRef]) -> NoReturn:
        # wtf is this condition
        if versioned_ref.type == ElementType.node:
            if ref_ways := tuple(ref for ref in used_by if ref.type == ElementType.way):
                raise APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'Node {versioned_ref.id} is still used by ways {",".join(str(ref.id) for ref in ref_ways)}.',
                )
            elif ref_relations := tuple(ref for ref in used_by if ref.type == ElementType.relation):
                raise APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'Node {versioned_ref.id} is still used by relations {",".join(str(ref.id) for ref in ref_relations)}.',
                )
            else:
                raise NotImplementedError(f'Unsupported element type {next(iter(used_by)).type!r}')
        elif versioned_ref.type == ElementType.way:
            if ref_relations := tuple(ref for ref in used_by if ref.type == ElementType.relation):
                raise APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'Way {versioned_ref.id} is still used by relations {",".join(str(ref.id) for ref in ref_relations)}.',
                )
            else:
                raise NotImplementedError(f'Unsupported element type {next(iter(used_by)).type!r}')
        elif versioned_ref.type == ElementType.relation:
            if ref_relations := tuple(ref for ref in used_by if ref.type == ElementType.relation):
                raise APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'The relation {versioned_ref.id} is used in relation ' f'{ref_relations[0].id}.',
                )
            else:
                raise NotImplementedError(f'Unsupported element type {next(iter(used_by)).type!r}')
        else:
            raise NotImplementedError(f'Unsupported element type {versioned_ref.type!r}')
