from src.models.base_enum import BaseEnum


class OSMChangeAction(BaseEnum):
    create = 'create'
    modify = 'modify'
    delete = 'delete'
