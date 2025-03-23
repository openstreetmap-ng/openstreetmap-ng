from typing import Annotated, TypedDict

from annotated_types import MaxLen, MinLen
from pydantic import TypeAdapter

from app.config import PYDANTIC_CONFIG
from app.models.types import ApplicationId, UserId, UserPrefKey, UserPrefVal
from app.validators.xml import XMLSafeValidator


class UserPref(TypedDict):
    user_id: UserId
    app_id: ApplicationId | None
    key: Annotated[
        UserPrefKey,
        MinLen(1),
        MaxLen(255),
        XMLSafeValidator,
    ]
    value: Annotated[
        UserPrefVal,
        MinLen(1),
        MaxLen(255),
        XMLSafeValidator,
    ]  # TODO: test validate size


# TODO: check use
UserPrefListValidator = TypeAdapter(list[UserPref], config=PYDANTIC_CONFIG)
