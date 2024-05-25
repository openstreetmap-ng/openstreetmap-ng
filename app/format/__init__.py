from app.format.api06_changeset import Changeset06Mixin
from app.format.api06_diff import Diff06Mixin
from app.format.api06_element import Element06Mixin
from app.format.api06_note import Note06Mixin
from app.format.api06_note_rss import NoteRSS06Mixin
from app.format.api06_tag import Tag06Mixin
from app.format.api06_trace import Trace06Mixin
from app.format.api06_user import User06Mixin
from app.format.api07_element import Element07Mixin
from app.format.leaflet_changeset import LeafletChangesetMixin
from app.format.leaflet_element import LeafletElementMixin
from app.format.leaflet_note import LeafletNoteMixin


class Format07(
    Element07Mixin,
): ...


class Format06(
    Changeset06Mixin,
    Element06Mixin,
    Note06Mixin,
    Diff06Mixin,
    Tag06Mixin,
    Trace06Mixin,
    User06Mixin,
): ...


class FormatRSS06(
    NoteRSS06Mixin,
): ...


class FormatLeaflet(
    LeafletChangesetMixin,
    LeafletElementMixin,
    LeafletNoteMixin,
): ...
