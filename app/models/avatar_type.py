from app.models.base_enum import BaseEnum


class AvatarType(BaseEnum):
    default = 'default'
    gravatar = 'gravatar'
    custom = 'custom'
