from operator import itemgetter
from typing import Self, Sequence

from argon2 import PasswordHasher
from argon2.profiles import RFC_9106_HIGH_MEMORY, RFC_9106_LOW_MEMORY

from models.base_enum import BaseEnum


class UserRole(BaseEnum):
    moderator = 'moderator'
    administrator = 'administrator'

    @staticmethod
    def get_changeset_max_size(roles: Sequence[Self]) -> int:
        if not roles:
            roles = [None]

        return max(_changeset_max_size[r] for r in roles)

    @staticmethod
    def get_password_hasher(roles: Sequence[Self]) -> PasswordHasher:
        if not roles:
            roles = [None]

        return max((_password_hasher[r] for r in roles), key=itemgetter(0))[1]


_changeset_max_size = {
    None: 10_000,
    UserRole.moderator: 20_000,
    UserRole.administrator: 20_000,
}


# first tuple element is priority
_password_hasher = {
    None: (0, PasswordHasher.from_parameters(RFC_9106_LOW_MEMORY)),
    UserRole.moderator: (100, PasswordHasher.from_parameters(RFC_9106_HIGH_MEMORY)),
    UserRole.administrator: (100, PasswordHasher.from_parameters(RFC_9106_HIGH_MEMORY)),
}
