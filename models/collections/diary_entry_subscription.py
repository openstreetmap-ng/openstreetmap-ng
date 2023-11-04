from typing import Annotated

from pydantic import Field

from models.collections.base import Base
from models.collections.base_sequential import SequentialId


class DiaryEntrySubscription(Base):
    user_id: Annotated[SequentialId, Field(frozen=True)]
    diary_entry_id: Annotated[SequentialId, Field(frozen=True)]
