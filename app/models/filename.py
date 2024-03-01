from typing import Annotated

from app.models.str import Str255
from app.validators.filename import FileNameValidator

FileName = Annotated[Str255, FileNameValidator]
