from collections.abc import Sequence
from typing import Annotated

from pydantic import PositiveInt

from app.models.db.base import Base
from app.models.db.trace_ import TraceVisibility
from app.models.types import Str255
from app.validators.filename import FileNameValidator
from app.validators.url import UrlSafeValidator


class TraceValidating(Base.Validating):
    user_id: PositiveInt
    name: Annotated[Str255, FileNameValidator]
    description: Str255
    visibility: TraceVisibility

    size: PositiveInt

    # defaults
    tags: Sequence[Annotated[Str255, UrlSafeValidator]] = ()
