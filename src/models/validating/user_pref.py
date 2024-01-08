from pydantic import PositiveInt

from src.models.db.base import Base
from src.models.str import Str255


class UserPrefValidating(Base.Validating):
    user_id: PositiveInt
    app_id: int | None
    key: Str255
    value: Str255
