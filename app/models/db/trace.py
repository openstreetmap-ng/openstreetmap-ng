from collections.abc import Container
from datetime import datetime
from typing import Literal, NewType, NotRequired, TypedDict

import numpy as np
from numpy.typing import NDArray
from shapely import MultiLineString

from app.limits import TRACE_TAG_MAX_LENGTH
from app.models.db.user import User, UserId
from app.models.scope import Scope
from app.models.types import StorageKey

TraceId = NewType('TraceId', int)
TraceVisibility = Literal['identifiable', 'public', 'trackable', 'private']


class TraceInit(TypedDict):
    user_id: UserId
    name: str
    description: str
    tags: list[str]  # TODO: validate size
    visibility: TraceVisibility
    file_id: StorageKey
    tracks: MultiLineString  # TODO: z-dimension
    capture_times: list[datetime | None] | None


class Trace(TraceInit):
    id: TraceId
    size: int
    created_at: datetime
    updated_at: datetime

    # runtime
    user: NotRequired[User]
    coords: NotRequired[NDArray[np.number]]


def trace_tags_from_str(s: str) -> list[str]:
    """Convert a string of tags to a list of tags."""
    if ',' in s:
        sep = ','
    else:
        # do as before for backwards compatibility
        # BUG: this produces weird behavior: 'a b, c' -> ['a b', 'c']; 'a b' -> ['a', 'b']
        sep = None

    # remove duplicates and preserve order
    result_set: set[str] = set()
    result: list[str] = []
    for tag in s.split(sep):
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


def trace_is_visible_to(trace: Trace, user: User | None, scopes: Container[Scope]) -> bool:
    """Check if the trace is visible to the user."""
    if trace_is_linked_to_user_on_site(trace):
        return True
    return (
        user is not None  #
        and trace['user_id'] == user['id']
        and 'read_gpx' in scopes
    )


#     @validates('tags')
#     def validate_tags(self, _: str, value: Collection[str]):
#         if len(value) > TRACE_TAGS_LIMIT:
#             raise ValueError(f'Too many trace tags ({len(value)} > {TRACE_TAGS_LIMIT})')
#         return value
#
#     @property
#     def tag_string(self) -> str:
#         return ', '.join(self.tags)
