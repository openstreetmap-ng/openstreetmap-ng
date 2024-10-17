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
    def from_kwargs(
        cls,
        *,
        read_prefs: bool = False,
        write_prefs: bool = False,
        write_api: bool = False,
        read_gpx: bool = False,
        write_gpx: bool = False,
        write_notes: bool = False,
        **_: bool,
    ) -> tuple['Scope', ...]:
        """
        Return the scopes from the given kwargs.

        Unsupported keys are ignored.

        >>> Scope.from_kwargs(read_prefs=True, write_api=True, unknown=True)
        (Scope.read_prefs, Scope.write_api)
        """
        result: list[Scope] = []
        if read_prefs:
            result.append(cls.read_prefs)
        if write_prefs:
            result.append(cls.write_prefs)
        if write_api:
            result.append(cls.write_api)
        if read_gpx:
            result.append(cls.read_gpx)
        if write_gpx:
            result.append(cls.write_gpx)
        if write_notes:
            result.append(cls.write_notes)
        return tuple(result)

    @classmethod
    def from_str(cls, s: str) -> tuple['Scope', ...]:
        """
        Get scopes from a string, where each scope is separated by a space.

        Only public scopes are resolved.

        >>> Scope.from_str('read_prefs write_api skip_authorization')
        (Scope.read_prefs, Scope.write_api)
        """
        return cls.from_kwargs(**{s: True for s in s.split() if s})


PUBLIC_SCOPES = (
    Scope.read_prefs,
    Scope.write_prefs,
    Scope.write_api,
    Scope.read_gpx,
    Scope.write_gpx,
    Scope.write_notes,
)
