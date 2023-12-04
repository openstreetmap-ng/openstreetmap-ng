from datetime import datetime
from typing import Annotated

from annotated_types import MaxLen

from limits import OAUTH1_NONCE_MAX_LENGTH
from models.db.base import Base


class OAuth1NonceValidating(Base.Validating):
    nonce: Annotated[str, MaxLen(OAUTH1_NONCE_MAX_LENGTH)]
    created_at: datetime
