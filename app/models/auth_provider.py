from enum import Enum
from typing import Literal


class AuthProvider(str, Enum):
    # openid = 'openid'
    google = 'google'
    facebook = 'facebook'
    microsoft = 'microsoft'
    github = 'github'
    wikimedia = 'wikimedia'  # TODO: migration, old value: wikipedia


AuthProviderAction = Literal['login', 'signup', 'settings']

__all__ = ('AuthProviderAction',)
