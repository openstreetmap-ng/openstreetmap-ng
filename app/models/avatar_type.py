from enum import Enum


class AvatarType(str, Enum):
    default = 'default'
    gravatar = 'gravatar'
    custom = 'custom'
