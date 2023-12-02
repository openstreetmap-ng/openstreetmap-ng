from models.db.base import Base
from models.str import EmptyStr255


class TagsValidating(Base.Validating):
    tags: dict[EmptyStr255, EmptyStr255]
