from pydantic import PositiveInt

from models.db.base import Base
from models.str import Str255


class UserPrefValidating(Base.Validating):
    user_id: PositiveInt
    app_id: int | None
    key: Str255
    value: Str255
