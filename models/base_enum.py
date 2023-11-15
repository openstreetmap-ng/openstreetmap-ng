from enum import StrEnum

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

# ConfigDict's use_enum_values=True is unpredictable
# see https://github.com/pydantic/pydantic/issues/6565


class BaseEnum(StrEnum):
    """
    Enum that is always serialized as a string.
    """

    @classmethod
    def __get_pydantic_core_schema__(cls, source: type, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        return core_schema.is_instance_schema(
            StrEnum,
            serialization=core_schema.to_string_ser_schema(),
        )
