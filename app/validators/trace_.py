from collections.abc import Sequence
from typing import Annotated

from pydantic import PositiveInt

from app.models.db.base import Base
from app.models.filename import FileName
from app.models.str import Str255
from app.models.trace_visibility import TraceVisibility
from app.validators.url import UrlSafeValidator


class TraceValidating(Base.Validating):
    user_id: PositiveInt
    name: FileName
    description: Str255
    visibility: TraceVisibility

    size: PositiveInt

    # defaults
    tags: Sequence[Annotated[Str255, UrlSafeValidator]] = ()
