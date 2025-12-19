from typing import TYPE_CHECKING, NoReturn, override

from starlette import status

from app.exceptions.api_error import APIError
from app.exceptions.element_mixin import ElementExceptionsMixin
from app.models.element import TypedElementId
from speedup import split_typed_element_id, split_typed_element_ids

if TYPE_CHECKING:
    from app.models.db.element import Element, ElementInit


class ElementExceptions06Mixin(ElementExceptionsMixin):
    @override
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
            detail=f'The {type} with the id {id} was not found',
        )

    @override
    def element_redacted(self, versioned_ref: tuple[TypedElementId, int]) -> NoReturn:
        self.element_not_found(versioned_ref)

    @override
    def element_redact_latest(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='Cannot redact current version of element, only historical versions may be redacted',
        )

    @override
    def element_already_deleted(self, element_ref: TypedElementId) -> NoReturn:
        type, id = split_typed_element_id(element_ref)
        raise APIError(
            status.HTTP_412_PRECONDITION_FAILED,
            detail=f'Cannot delete an already deleted {type} with id {id}.',
        )

    @override
    def element_changeset_missing(self) -> NoReturn:
        raise APIError(
            status.HTTP_409_CONFLICT,
            detail='You need to supply a changeset to be able to make a change',
        )

    @override
    def element_version_conflict(
        self, element: 'Element | ElementInit', local_version: int
    ) -> NoReturn:
        type, id = split_typed_element_id(element['typed_id'])
        raise APIError(
            status.HTTP_409_CONFLICT,
            detail=f'Version mismatch: Provided {element["version"] - 1}, server had: {local_version} of {type} {id}',
        )

    @override
    def element_member_not_found(
        self, parent_ref: TypedElementId, member_ref: TypedElementId
    ) -> NoReturn:
        parent_type, parent_id = split_typed_element_id(parent_ref)
        member_type, member_id = split_typed_element_id(member_ref)

        if parent_type == 'way':
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail=f'Way {parent_id} requires the nodes with id in ({member_id}), which either do not exist, or are not visible.',
            )

        if parent_type == 'relation':
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail=f'Relation with id {parent_id} cannot be saved due to {member_type} with id {member_id}',
            )

        raise NotImplementedError(f'Unsupported element type {parent_type!r}')

    @override
    def element_in_use(
        self, element_ref: TypedElementId, used_by: list[TypedElementId]
    ) -> NoReturn:
        # wtf is this condition
        type, id = split_typed_element_id(element_ref)
        used_by_type_id = split_typed_element_ids(used_by)

        if type == 'node':
            ref_ways = [type_id for type_id in used_by_type_id if type_id[0] == 'way']
            if ref_ways:
                raise APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'Node {id} is still used by ways {",".join(str(ref[1]) for ref in ref_ways)}.',
                )

            ref_relations = [
                type_id for type_id in used_by_type_id if type_id[0] == 'relation'
            ]
            if ref_relations:
                raise APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'Node {id} is still used by relations {",".join(str(ref[1]) for ref in ref_relations)}.',
                )

            raise NotImplementedError(
                f'Unsupported element type {next(iter(used_by_type_id))[0]!r}'
            )

        if type == 'way':
            ref_relations = [
                type_id for type_id in used_by_type_id if type_id[0] == 'relation'
            ]
            if ref_relations:
                raise APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'Way {id} is still used by relations {",".join(str(ref[1]) for ref in ref_relations)}.',
                )

            raise NotImplementedError(
                f'Unsupported element type {next(iter(used_by_type_id))[0]!r}'
            )

        if type == 'relation':
            ref_relations = [
                type_id for type_id in used_by_type_id if type_id[0] == 'relation'
            ]
            if ref_relations:
                raise APIError(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f'The relation {id} is used in relation {ref_relations[0][1]}.',
                )

            raise NotImplementedError(
                f'Unsupported element type {next(iter(used_by_type_id))[0]!r}'
            )

        raise NotImplementedError(f'Unsupported element type {type!r}')
