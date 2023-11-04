from typing import Annotated

from pydantic import Field

from models.collections.base import Base
from models.collections.base_sequential import SequentialId

# TODO: unique index


class ChangesetSubscription(Base):
    user_id: Annotated[SequentialId, Field(frozen=True)]
    changeset_id: Annotated[SequentialId, Field(frozen=True)]
