from datetime import datetime
from typing import Annotated, NotRequired, TypedDict

import numpy as np
from annotated_types import MaxLen, MinLen
from numpy.typing import NDArray
from pydantic import TypeAdapter
from shapely import MultiLineString

from app.config import (
    PYDANTIC_CONFIG,
    TRACE_DESCRIPTION_MAX_LENGTH,
    TRACE_NAME_MAX_LENGTH,
    TRACE_TAG_MAX_LENGTH,
    TRACE_TAGS_LIMIT,
)
from app.lib.auth_context import auth_scopes, auth_user
from app.models.db.user import UserDisplay, user_is_moderator
from app.models.proto.trace_types import Visibility
from app.models.types import StorageKey, TraceId, UserId
from app.validators.filename import FileNameValidator
from app.validators.geometry import GeometryValidator
from app.validators.url import UrlSafeValidator
from app.validators.xml import XMLSafeValidator


class TraceMetaInit(TypedDict):
    __pydantic_config__ = PYDANTIC_CONFIG  # type: ignore

    name: Annotated[
        str,
        FileNameValidator,
        MinLen(1),
        MaxLen(TRACE_NAME_MAX_LENGTH),
        XMLSafeValidator,
    ]
    description: Annotated[
        str,
        MinLen(1),
        MaxLen(TRACE_DESCRIPTION_MAX_LENGTH),
        XMLSafeValidator,
    ]
    tags: Annotated[
        list[
            Annotated[
                str,
                MinLen(1),
                MaxLen(TRACE_TAG_MAX_LENGTH),
                XMLSafeValidator,
                UrlSafeValidator,
            ]
        ],
        MaxLen(TRACE_TAGS_LIMIT),
    ]
    visibility: Visibility


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


def parse_trace_tags(tags: str | None) -> list[str]:
    if not tags:
        return []

    # Legacy API 0.6 accepts comma-separated values and falls back to whitespace
    # splitting when no comma is present.
    separator = ',' if ',' in tags else None
    return tags.split(separator, TRACE_TAGS_LIMIT)


def normalize_trace_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []

    if len(tags) > TRACE_TAGS_LIMIT:
        raise ValueError(f'Too many trace tags, current limit is {TRACE_TAGS_LIMIT}')

    normalized: list[str] = []
    seen = set[str]()

    for raw_tag in tags:
        tag = raw_tag.strip()
        if not tag:
            continue
        if len(tag) > TRACE_TAG_MAX_LENGTH:
            raise ValueError(
                f'Trace tag too long, current limit is {TRACE_TAG_MAX_LENGTH}'
            )
        if tag in seen:
            continue
        seen.add(tag)
        normalized.append(tag)

    return normalized


def trace_is_linked_to_user_in_api(trace: Trace):
    """Check if the trace is linked to the user in the API."""
    return trace['visibility'] == 'identifiable'


def trace_is_linked_to_user_on_site(trace: Trace):
    """Check if the trace is linked to the user on the site."""
    return trace['visibility'] in {'identifiable', 'public'}


def trace_is_timestamps_via_api(trace: Trace):
    """Check if the trace timestamps are tracked via the API."""
    return trace['visibility'] in {'identifiable', 'trackable'}


def trace_is_visible(trace: Trace):
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
