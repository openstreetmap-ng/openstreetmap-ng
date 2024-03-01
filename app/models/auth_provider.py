from enum import Enum


class AuthProvider(str, Enum):
    openid = 'openid'
    google = 'google'
    facebook = 'facebook'
    microsoft = 'microsoft'
    github = 'github'
    wikipedia = 'wikipedia'
