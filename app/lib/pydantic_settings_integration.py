import logging
from collections.abc import Callable
from sys import modules
from typing import Any, get_type_hints

from pydantic import create_model
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


# noinspection PyDefaultArgument
def pydantic_settings_integration(
    caller_name: str,
    caller_globals: dict[str, Any],
    /,
    config: SettingsConfigDict = BaseSettings.model_config,
    name_filter: Callable[[str], bool] = lambda name: name[:1] != '_'
    and name.isupper(),
) -> None:
    """
    Introspects the calling module's globals, creates a dynamic Pydantic
    BaseSettings model, loads settings from environment/.env files, and updates
    the original global variables with the validated values.
    """
    filtered_globals = {k: v for k, v in caller_globals.items() if name_filter(k)}
    if not filtered_globals:
        logging.warning('No settings found in %s matching the filter', caller_name)
        return

    type_hints = get_type_hints(modules[caller_name], filtered_globals)
    fields: dict[str, tuple[type, Any]] = {
        name: (
            type_hints.get(name, Any if isinstance(value, FieldInfo) else type(value)),
            value,
        )
        for name, value in filtered_globals.items()
    }

    model_instance = create_model(
        f'{caller_name}_DynamicSettings',
        __base__=type(
            f'{caller_name}_DynamicBaseSettings',
            (BaseSettings,),
            {'model_config': config},
        ),
        **fields,  # type: ignore
    )()

    for name in filtered_globals:
        caller_globals[name] = getattr(model_instance, name)
