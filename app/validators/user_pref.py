from pydantic import PositiveInt

from app.models.db.base import Base
from app.models.str import Str255


class UserPrefValidating(Base.Validating):
    user_id: PositiveInt
    app_id: int | None
    key: Str255
    value: Str255
