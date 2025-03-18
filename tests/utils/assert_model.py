from typing import Annotated, Any, get_origin

from annotated_types import Predicate
from pydantic import ConfigDict, create_model


def assert_model(
    data: dict,
    fields: dict[str, Any],
    /,
    *,
    strict: bool = False,
) -> None:
    """
    Validate a dictionary structure against a set of validators.
    :param data: The input dictionary to validate.
    :param fields: A dictionary mapping field names to Pydantic validators.
    :param strict: If True, no extra fields are allowed in the input.
    """
    field_definitions = {
        field_name: (
            (
                validator
                if isinstance(validator, type) or get_origin(validator) is not None
                else Annotated[type(validator), Predicate(lambda x, v=validator: x == v)]
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
