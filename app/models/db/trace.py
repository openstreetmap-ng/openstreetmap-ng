from datetime import datetime
from typing import Annotated, Literal, NotRequired, TypedDict

import numpy as np
from annotated_types import MaxLen, MinLen
from numpy.typing import NDArray
from pydantic import TypeAdapter
from shapely import MultiLineString

from app.config import PYDANTIC_CONFIG
from app.limits import TRACE_TAG_MAX_LENGTH, TRACE_TAGS_LIMIT
from app.models.db.user import User, UserDisplay
from app.models.scope import Scope
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
    segments: Annotated[MultiLineString, GeometryValidator]  # TODO: z-dimension
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


def trace_tags_from_str(s: str | None) -> list[str]:
    """Convert a string of tags to a list of tags."""
    if not s:
        return []

    if ',' in s:
        sep = ','
    else:
        # do as before for backwards compatibility
        # BUG: this produces weird behavior: 'a b, c' -> ['a b', 'c']; 'a b' -> ['a', 'b']
        sep = None

    tags = s.split(sep, TRACE_TAGS_LIMIT)
    if len(tags) > TRACE_TAGS_LIMIT:
        raise ValueError(f'Too many trace tags, current limit is {TRACE_TAGS_LIMIT}')

    # remove duplicates and preserve order
    result_set: set[str] = set()
    result: list[str] = []

    for tag in tags:
        tag = tag.strip()[:TRACE_TAG_MAX_LENGTH].strip()
        if tag and (tag not in result_set):
            result_set.add(tag)
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


def trace_is_visible_to(trace: Trace, user: User | None, scopes: tuple[Scope, ...]) -> bool:
    """Check if the trace is visible to the user."""
    return trace_is_linked_to_user_on_site(trace) or (
        user is not None  #
        and trace['user_id'] == user['id']
        and 'read_gpx' in scopes
    )
