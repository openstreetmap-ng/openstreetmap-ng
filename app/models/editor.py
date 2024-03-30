from enum import Enum


class Editor(str, Enum):
    id = 'id'
    rapid = 'rapid'
    remote = 'remote'


DEFAULT_EDITOR = Editor.id
