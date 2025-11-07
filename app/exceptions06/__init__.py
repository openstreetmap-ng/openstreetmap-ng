from app.exceptions import Exceptions
from app.exceptions06.auth_mixin import AuthExceptions06Mixin
from app.exceptions06.changeset_mixin import ChangesetExceptions06Mixin
from app.exceptions06.diff_mixin import DiffExceptions06Mixin
from app.exceptions06.element_mixin import ElementExceptions06Mixin
from app.exceptions06.map_mixin import MapExceptions06Mixin
from app.exceptions06.note_mixin import NoteExceptions06Mixin
from app.exceptions06.request_mixin import RequestExceptions06Mixin
from app.exceptions06.trace_mixin import TraceExceptions06Mixin
from app.exceptions06.user_mixin import UserExceptions06Mixin


class Exceptions06(
    Exceptions,
    AuthExceptions06Mixin,
    ChangesetExceptions06Mixin,
    DiffExceptions06Mixin,
    ElementExceptions06Mixin,
    MapExceptions06Mixin,
    NoteExceptions06Mixin,
    RequestExceptions06Mixin,
    TraceExceptions06Mixin,
    UserExceptions06Mixin,
): ...
