from typing import Annotated

from pydantic import Field

from models.db.base import Base
from models.db.base_sequential import SequentialId

# TODO: unique index


class DiaryEntrySubscription(Base):
    user_id: Annotated[SequentialId, Field(frozen=True)]
    diary_entry_id: Annotated[SequentialId, Field(frozen=True)]
