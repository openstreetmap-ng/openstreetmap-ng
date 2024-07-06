from collections.abc import Collection
from typing import TYPE_CHECKING, NoReturn, override

from starlette import status

from app.exceptions.api_error import APIError
from app.exceptions.element_mixin import ElementExceptionsMixin
from app.models.element_ref import ElementRef, VersionedElementRef

if TYPE_CHECKING:
    from app.models.db.element import Element


class ElementExceptions06Mixin(ElementExceptionsMixin):
    @override
    def element_not_found(self, element_ref: ElementRef | VersionedElementRef) -> NoReturn:
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'The {element_ref.type} with the id {element_ref.id} was not found',
        )

    @override
    def element_redacted(self, versioned_ref: VersionedElementRef) -> NoReturn:
        self.element_not_found(versioned_ref)

    @override
    def element_redact_latest(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='Cannot redact current version of element, only historical versions may be redacted',
        )

    @override
    def element_already_deleted(self, element: 'Element') -> NoReturn:
        raise APIError(
            status.HTTP_412_PRECONDITION_FAILED,
            detail=f'Cannot delete an already deleted {element.type} with id {element.id}.',
        )

    @override
    def element_changeset_missing(self) -> NoReturn:
        raise APIError(status.HTTP_409_CONFLICT, detail='You need to supply a changeset to be able to make a change')

    @override
    def element_version_conflict(self, element: 'Element', local_version: int) -> NoReturn:
        raise APIError(
            status.HTTP_409_CONFLICT,
            detail=f'Version mismatch: Provided {element.version - 1}, server had: {local_version} of {element.type} {element.id}',
        )

    @override
    def element_member_not_found(self, parent_ref: ElementRef, member_ref: ElementRef) -> NoReturn:
        if parent_ref.type == 'way':
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail=f'Way {parent_ref.id} requires the nodes with id in ({member_ref.id}), which either do not exist, or are not visible.',
            )
        elif parent_ref.type == 'relation':
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail=f'Relation with id {parent_ref.id} cannot be saved due to {member_ref.type} with id {member_ref.id}',
            )
        else:
            raise NotImplementedError(f'Unsupported element type {parent_ref.type!r}')

    @override
    def element_in_use(self, element: 'Element', used_by: Collection[ElementRef]) -> NoReturn:
        # wtf is this condition
        if element.type == 'node':
            if ref_ways := tuple(ref for ref in used_by if ref.type == 'way'):
                raise APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'Node {element.id} is still used by ways {",".join(str(ref.id) for ref in ref_ways)}.',
                )
            elif ref_relations := tuple(ref for ref in used_by if ref.type == 'relation'):
                raise APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'Node {element.id} is still used by relations {",".join(str(ref.id) for ref in ref_relations)}.',
                )
            else:
                raise NotImplementedError(f'Unsupported element type {next(iter(used_by)).type!r}')
        elif element.type == 'way':
            if ref_relations := tuple(ref for ref in used_by if ref.type == 'relation'):
                raise APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'Way {element.id} is still used by relations {",".join(str(ref.id) for ref in ref_relations)}.',
                )
            else:
                raise NotImplementedError(f'Unsupported element type {next(iter(used_by)).type!r}')
        elif element.type == 'relation':
            if ref_relations := tuple(ref for ref in used_by if ref.type == 'relation'):
                raise APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'The relation {element.id} is used in relation ' f'{ref_relations[0].id}.',
                )
            else:
                raise NotImplementedError(f'Unsupported element type {next(iter(used_by)).type!r}')
        else:
            raise NotImplementedError(f'Unsupported element type {element.type!r}')
