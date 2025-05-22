from typing import TYPE_CHECKING, NoReturn, override

from starlette import status

from app.exceptions.api_error import APIError
from app.exceptions.diff_mixin import DiffExceptionsMixin
from optimized import split_typed_element_id

if TYPE_CHECKING:
    from app.models.db.element import ElementInit


class DiffExceptions06Mixin(DiffExceptionsMixin):
    @override
    def diff_multiple_changesets(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='Only one changeset can be modified at a time',
        )

    @override
    def diff_unsupported_action(self, action: str) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Unknown action {action}, choices are create, modify, delete',
        )

    @override
    def diff_create_bad_id(self, element: 'ElementInit') -> NoReturn:
        type = split_typed_element_id(element['typed_id'])[0]
        if type == 'node':
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail='Cannot create node: data is invalid.',
            )
        elif type == 'way':
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail='Cannot create way: data is invalid.',
            )
        elif type == 'relation':
            raise APIError(
                status.HTTP_412_PRECONDITION_FAILED,
                detail='Cannot create relation: data or member data is invalid.',
            )
        else:
            raise NotImplementedError(f'Unsupported element type {type!r}')

    @override
    def diff_update_bad_version(self, element: 'ElementInit') -> NoReturn:
        raise APIError(
            status.HTTP_412_PRECONDITION_FAILED,
            detail=f'Update action requires version >= 1, got {element["version"] - 1}',
        )
