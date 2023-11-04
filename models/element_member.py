from typing import Annotated

from pydantic import BaseModel, Field

from models.str import EmptyStr255
from models.typed_element_ref import TypedElementRef


class ElementMember(BaseModel):
    ref: Annotated[TypedElementRef, Field(frozen=True)]
    role: Annotated[EmptyStr255, Field(frozen=True)]
