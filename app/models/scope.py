from enum import Enum


class Scope(str, Enum):
    read_prefs = 'read_prefs'
    write_prefs = 'write_prefs'
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

    @classmethod
    def get_basic(cls) -> tuple['Scope', ...]:
        return (
            cls.read_prefs,
            cls.write_prefs,
            cls.write_api,
            cls.read_gpx,
            cls.write_gpx,
            cls.write_notes,
        )
