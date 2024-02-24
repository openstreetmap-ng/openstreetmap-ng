from enum import Enum


class UserStatus(str, Enum):
    pending = 'pending'
    active = 'active'
