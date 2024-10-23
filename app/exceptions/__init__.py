from app.exceptions.auth_mixin import AuthExceptionsMixin
from app.exceptions.changeset_mixin import ChangesetExceptionsMixin
from app.exceptions.diff_mixin import DiffExceptionsMixin
from app.exceptions.element_mixin import ElementExceptionsMixin
from app.exceptions.image_mixin import ImageExceptionsMixin
from app.exceptions.map_mixin import MapExceptionsMixin
from app.exceptions.message_mixin import MessageExceptionsMixin
from app.exceptions.note_mixin import NoteExceptionsMixin
from app.exceptions.request_mixin import RequestExceptionsMixin
from app.exceptions.trace_mixin import TraceExceptionsMixin
from app.exceptions.user_mixin import UserExceptionsMixin


class Exceptions(
    AuthExceptionsMixin,
    ChangesetExceptionsMixin,
    DiffExceptionsMixin,
    ElementExceptionsMixin,
    ImageExceptionsMixin,
    MapExceptionsMixin,
    MessageExceptionsMixin,
    NoteExceptionsMixin,
    RequestExceptionsMixin,
    TraceExceptionsMixin,
    UserExceptionsMixin,
): ...
