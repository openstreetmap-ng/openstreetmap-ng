from app.models.base_enum import BaseEnum


class AuthProvider(BaseEnum):
    openid = 'openid'
    google = 'google'
    facebook = 'facebook'
    microsoft = 'microsoft'
    github = 'github'
    wikipedia = 'wikipedia'


ALL_AUTH_PROVIDERS = tuple(e for e in AuthProvider)
