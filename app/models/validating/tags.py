from app.models.db.base import Base
from app.models.str import EmptyStr255


class TagsValidating(Base.Validating):
    tags: dict[EmptyStr255, EmptyStr255]
