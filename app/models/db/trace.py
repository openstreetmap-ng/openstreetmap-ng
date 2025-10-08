from datetime import datetime
from typing import Annotated, Literal, NotRequired, TypedDict

import numpy as np
from annotated_types import MaxLen, MinLen
from numpy.typing import NDArray
from pydantic import TypeAdapter
from shapely import MultiLineString

from app.config import PYDANTIC_CONFIG, TRACE_TAG_MAX_LENGTH, TRACE_TAGS_LIMIT
from app.lib.auth_context import auth_scopes, auth_user
from app.models.db.user import UserDisplay, user_is_moderator
from app.models.types import StorageKey, TraceId, UserId
from app.validators.filename import FileNameValidator
from app.validators.geometry import GeometryValidator
from app.validators.url import UrlSafeValidator
from app.validators.xml import XMLSafeValidator

TraceVisibility = Literal['identifiable', 'public', 'trackable', 'private']


class TraceMetaInit(TypedDict):
    __pydantic_config__ = PYDANTIC_CONFIG  # type: ignore

    name: Annotated[
        str,
        FileNameValidator,
        MinLen(1),
        MaxLen(255),
        XMLSafeValidator,
    ]
    description: Annotated[
        str,
        MinLen(1),
        MaxLen(255),
        XMLSafeValidator,
    ]
    tags: list[
        Annotated[
            str,
            MinLen(1),
            MaxLen(255),
            XMLSafeValidator,
            UrlSafeValidator,
        ]
    ]  # TODO: validate size
    visibility: TraceVisibility


class TraceInit(TraceMetaInit):
    user_id: UserId
    file_id: StorageKey
    size: int
    segments: Annotated[MultiLineString, GeometryValidator]
    elevations: list[float | None] | None
    capture_times: list[datetime | None] | None


TraceMetaInitValidator = TypeAdapter(TraceMetaInit)
TraceInitValidator = TypeAdapter(TraceInit)


class Trace(TraceInit):
    id: TraceId
    created_at: datetime
    updated_at: datetime

    # runtime
    user: NotRequired[UserDisplay]
    coords: NotRequired[NDArray[np.number]]


def validate_trace_tags(tags: str | list[str] | None) -> list[str]:
    if not tags:
        return []

    if isinstance(tags, str):
        # do as before for backwards compatibility
        # BUG: this produces weird behavior: 'a b, c' -> ['a b', 'c']; 'a b' -> ['a', 'b']
        sep = ',' if ',' in tags else None
        tags = tags.split(sep, TRACE_TAGS_LIMIT)

    if len(tags) > TRACE_TAGS_LIMIT:
        raise ValueError(f'Too many trace tags, current limit is {TRACE_TAGS_LIMIT}')

    seen = set[str]()
    result = []

    for tag in tags:
        tag = tag.strip()[:TRACE_TAG_MAX_LENGTH].strip()
        if tag and (tag not in seen):
            seen.add(tag)
            result.append(tag)

    return result


def trace_is_linked_to_user_in_api(trace: Trace) -> bool:
    """Check if the trace is linked to the user in the API."""
    return trace['visibility'] == 'identifiable'


def trace_is_linked_to_user_on_site(trace: Trace) -> bool:
    """Check if the trace is linked to the user on the site."""
    return trace['visibility'] in {'identifiable', 'public'}


def trace_is_timestamps_via_api(trace: Trace) -> bool:
    """Check if the trace timestamps are tracked via the API."""
    return trace['visibility'] in {'identifiable', 'trackable'}


def trace_is_visible(trace: Trace) -> bool:
    """Check if the trace is visible to the current user."""
    return (
        trace_is_linked_to_user_on_site(trace)
        or (
            # user is authorized owner
            (user := auth_user()) is not None  #
            and trace['user_id'] == user['id']
            and 'read_gpx' in auth_scopes()
        )
        or user_is_moderator(user)
    )
