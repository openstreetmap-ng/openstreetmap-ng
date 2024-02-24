from enum import Enum


class AuthProvider(str, Enum):
    openid = 'openid'
    google = 'google'
    facebook = 'facebook'
    microsoft = 'microsoft'
    github = 'github'
    wikipedia = 'wikipedia'


ALL_AUTH_PROVIDERS = tuple(e for e in AuthProvider)
