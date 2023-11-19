from typing import Annotated

from models.str import Str255
from validators.filename import FileNameValidator

FileName = Annotated[
    Str255,
    FileNameValidator,
]
