from models.base_enum import BaseEnum


class UserAvatarType(BaseEnum):
    default = 'default'
    gravatar = 'gravatar'
    custom = 'custom'
