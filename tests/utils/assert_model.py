from collections.abc import Mapping, Sequence
from typing import Annotated, Any, get_origin

from annotated_types import BaseMetadata, GroupedMetadata, Predicate
from pydantic import ConfigDict, create_model


def _assert_list(data: Sequence, validators: list):
    for item, validator in zip(data, validators, strict=True):
        if isinstance(validator, dict):
            assert_model(item, validator)
        elif isinstance(validator, list):
            _assert_list(item, validator)
        else:
            assert item == validator


def assert_model(
    data: Mapping,
    fields: Mapping[str, Any],
    /,
    *,
    strict: bool = False,
):
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
    field_definitions = {}

    for field_name, validator in fields.items():
        # Handle types and generic types (e.g., str, int, List[str])
        if isinstance(validator, type) or get_origin(validator) is not None:
            field_definition = validator

        # Handle Pydantic validators (e.g., Gt(5), Len(4, 4))
        elif isinstance(validator, BaseMetadata | GroupedMetadata):
            field_definition = Annotated[Any, validator]

        # Handle nested dict validation
        elif isinstance(validator, dict):
            field_definition = Annotated[
                dict,
                Predicate(lambda x, v=validator: assert_model(x, v) or True),
            ]

        # Handle list validation
        elif isinstance(validator, list):
            field_definition = Annotated[
                list,
                Predicate(lambda x, v=validator: _assert_list(x, v) or True),
            ]

        # Handle literal values (e.g., True, 42, 'open')
        else:
            field_definition = Annotated[
                type(validator),
                Predicate(lambda x, v=validator: x == v),
            ]

        field_definitions[field_name] = (field_definition, ...)

    create_model(
        'AssertModel',
        **field_definitions,
        __config__=ConfigDict(
            extra='forbid' if strict else 'allow',
            arbitrary_types_allowed=True,
            allow_inf_nan=False,
            strict=True,
            cache_strings='keys',
        ),
    ).model_validate(data)
