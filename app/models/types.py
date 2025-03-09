from typing import Annotated, NewType

from annotated_types import Interval
from pydantic import SecretStr

Email = NewType('Email', str)
DisplayName = NewType('DisplayName', str)

ClientId = NewType('ClientId', str)
LocaleCode = NewType('LocaleCode', str)
Password = NewType('Password', SecretStr)
StorageKey = NewType('StorageKey', str)
Uri = NewType('Uri', str)

Longitude = Annotated[float, Interval(ge=-180, le=180)]
Latitude = Annotated[float, Interval(ge=-90, le=90)]
Zoom = Annotated[int, Interval(ge=0, le=25)]
