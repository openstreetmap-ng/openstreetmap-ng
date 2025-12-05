from app.format.api06_changeset import Changeset06Mixin
from app.format.api06_changeset_rss import ChangesetRSS06Mixin
from app.format.api06_diff import Diff06Mixin
from app.format.api06_element import Element06Mixin
from app.format.api06_note import Note06Mixin
from app.format.api06_note_rss import NoteRSS06Mixin
from app.format.api06_tag import Tag06Mixin
from app.format.api06_trace import Trace06Mixin
from app.format.api06_user import User06Mixin
from app.format.api07_element import Element07Mixin
from app.format.render_changeset import RenderChangesetMixin
from app.format.render_element import RenderElementMixin
from app.format.render_note import RenderNoteMixin


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
    ChangesetRSS06Mixin,
    NoteRSS06Mixin,
): ...


class FormatRender(
    RenderChangesetMixin,
    RenderElementMixin,
    RenderNoteMixin,
): ...
