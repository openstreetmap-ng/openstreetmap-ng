from enum import Enum


class UserStatus(str, Enum):
    pending_terms = 'pending_terms'
    pending_activation = 'pending_activation'
    active = 'active'
