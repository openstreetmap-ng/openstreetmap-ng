from typing import Annotated

from src.models.str import Str255
from src.validators.filename import FileNameValidator

FileName = Annotated[
    Str255,
    FileNameValidator,
]
