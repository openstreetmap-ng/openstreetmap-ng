from app.format06.changeset_mixin import Changeset06Mixin
from app.format06.element_mixin import Element06Mixin
from app.format06.geometry_mixin import Geometry06Mixin
from app.format06.note_mixin import Note06Mixin
from app.format06.note_rss_mixin import NoteRSS06Mixin
from app.format06.osmchange_mixin import OsmChange06Mixin
from app.format06.tag_mixin import Tag06Mixin
from app.format06.trace_mixin import Trace06Mixin
from app.format06.user_mixin import User06Mixin


class Format06(
    Changeset06Mixin,
    Element06Mixin,
    Geometry06Mixin,
    Note06Mixin,
    OsmChange06Mixin,
    Tag06Mixin,
    Trace06Mixin,
    User06Mixin,
):
    ...


class FormatRSS06(NoteRSS06Mixin):
    ...
