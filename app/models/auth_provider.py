from enum import Enum


class AuthProvider(str, Enum):
    openid = 'openid'
    google = 'google'
    facebook = 'facebook'
    microsoft = 'microsoft'
    github = 'github'
    wikimedia = 'wikimedia'  # TODO: migration, old value: wikipedia


class AuthProviderAction(str, Enum):
    login = 'login'
    signup = 'signup'
    settings = 'settings'
