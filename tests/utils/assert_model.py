from collections.abc import Mapping
from typing import Annotated, Any, get_origin

from annotated_types import BaseMetadata, GroupedMetadata, Predicate
from pydantic import ConfigDict, create_model


def assert_model(
    data: Mapping,
    fields: Mapping[str, Any],
    /,
    *,
    strict: bool = False,
) -> None:
    """
    Assert that a dictionary matches expected field types and values.

    This function provides a unified way to validate data structures using three types of validators:
    - **Types**: Standard Python types (str, int, datetime) or Pydantic types (PositiveInt)
    - **Constraints**: Pydantic validators (Gt(5), Len(4, 4), Range(0, 100))
    - **Literals**: Exact values that must match ('open', True, 42)

    :param data: Dictionary to validate
    :param fields: Mapping of field names to validators
    :param strict: If True, forbid extra fields not specified in validators

    >>> assert_model(changeset, {
    ...     '@id': PositiveInt,           # Type validation
    ...     '@updated_at': Gt(last_time), # Constraint validation
    ...     '@open': True,                # Literal validation
    ... })
    """
    field_definitions = {
        field_name: (
            (
                validator
                if isinstance(validator, type) or get_origin(validator) is not None
                else (
                    Annotated[Any, validator]
                    if isinstance(validator, BaseMetadata | GroupedMetadata)
                    else Annotated[
                        type(validator), Predicate(lambda x, v=validator: x == v)
                    ]
                )
            ),
            ...,
        )
        for field_name, validator in fields.items()
    }

    create_model(
        'AssertModel',
        **field_definitions,  # type: ignore
        __config__=ConfigDict(
            extra='forbid' if strict else 'allow',
            arbitrary_types_allowed=True,
            allow_inf_nan=False,
            strict=True,
            cache_strings='keys',
        ),
    ).model_validate(data)
