from enum import Enum


class TagFormat(str, Enum):
    default = 'default'
    color = 'color'
    email = 'email'
    phone = 'phone'
    url = 'url'
