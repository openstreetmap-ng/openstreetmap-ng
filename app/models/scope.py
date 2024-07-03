from enum import Enum


class Scope(str, Enum):
    read_prefs = 'read_prefs'
    write_prefs = 'write_prefs'
    write_diary = 'write_diary'
    write_api = 'write_api'
    read_gpx = 'read_gpx'
    write_gpx = 'write_gpx'
    write_notes = 'write_notes'

    # additional scopes
    read_email = 'read_email'
    skip_authorization = 'skip_authorization'

    web_user = 'web_user'

    # role-specific scopes
    role_moderator = 'role_moderator'
    role_administrator = 'role_administrator'


BASIC_SCOPES = (
    Scope.read_prefs,
    Scope.write_prefs,
    Scope.write_diary,
    Scope.write_api,
    Scope.read_gpx,
    Scope.write_gpx,
    Scope.write_notes,
)
