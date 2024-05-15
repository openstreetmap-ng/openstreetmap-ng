from datetime import datetime
from typing import Annotated

from annotated_types import MaxLen

from app.limits import OAUTH1_NONCE_MAX_LENGTH
from app.models.db.base import Base


class OAuth1NonceValidating(Base.Validating):
    nonce: Annotated[str, MaxLen(OAUTH1_NONCE_MAX_LENGTH)]
    created_at: datetime
