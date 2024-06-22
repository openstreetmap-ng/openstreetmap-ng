from app.exceptions.auth_mixin import AuthExceptionsMixin
from app.exceptions.avatar_mixin import AvatarExceptionsMixin
from app.exceptions.changeset_mixin import ChangesetExceptionsMixin
from app.exceptions.diff_mixin import DiffExceptionsMixin
from app.exceptions.element_mixin import ElementExceptionsMixin
from app.exceptions.map_mixin import MapExceptionsMixin
from app.exceptions.note_mixin import NoteExceptionsMixin
from app.exceptions.request_mixin import RequestExceptionsMixin
from app.exceptions.trace_mixin import TraceExceptionsMixin
from app.exceptions.user_mixin import UserExceptionsMixin


class Exceptions(
    AuthExceptionsMixin,
    AvatarExceptionsMixin,
    ChangesetExceptionsMixin,
    DiffExceptionsMixin,
    ElementExceptionsMixin,
    MapExceptionsMixin,
    NoteExceptionsMixin,
    RequestExceptionsMixin,
    TraceExceptionsMixin,
    UserExceptionsMixin,
): ...
