from models.base_enum import BaseEnum


class EditorName(BaseEnum):
    potlach = 'potlach'
    potlatch2 = 'potlatch2'
    id = 'id'
    remote = 'remote'


ALL_EDITOR_NAMES = [e.value for e in EditorName]
AVAILABLE_EDITOR_NAMES = [EditorName.id.value, EditorName.remote.value]
RECOMMENDED_EDITOR_NAMES = [EditorName.id.value, EditorName.remote.value]
