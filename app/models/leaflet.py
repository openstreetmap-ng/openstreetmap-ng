from collections.abc import Collection

import msgspec


class ChangesetLeaflet(msgspec.Struct):
    id: int
    geom: Collection[Collection[float]]  # [[minLon, minLat, maxLon, maxLat], ...]
    user_name: str | None
    user_avatar: str | None
    closed: bool
    timeago: str
    comment: str | None
    num_comments: int


class NoteLeaflet(msgspec.Struct):
    id: int
    geom: Collection[float]  # [lat, lon]
    text: str
    open: bool
