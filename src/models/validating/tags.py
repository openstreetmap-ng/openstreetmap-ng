from src.models.db.base import Base
from src.models.str import EmptyStr255


class TagsValidating(Base.Validating):
    tags: dict[EmptyStr255, EmptyStr255]
