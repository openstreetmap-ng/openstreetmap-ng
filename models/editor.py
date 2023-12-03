from models.base_enum import BaseEnum


class Editor(BaseEnum):
    id = 'id'
    remote = 'remote'


ALL_EDITORS = tuple(e for e in Editor)

# available in user settings
AVAILABLE_EDITORS = ALL_EDITORS

# recommended under edit dropdown
RECOMMENDED_EDITORS = (Editor.id, Editor.remote)
