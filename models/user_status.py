from models.base_enum import BaseEnum


class UserStatus(BaseEnum):
    pending = 'pending'
    active = 'active'
    confirmed = 'confirmed'
