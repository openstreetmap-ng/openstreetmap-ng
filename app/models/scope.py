from typing import Literal

Scope = Literal[
    'read_prefs',
    'write_prefs',
    'write_api',
    'read_gpx',
    'write_gpx',
    'write_notes',
    # additional scopes
    'read_email',
    'skip_authorization',
    'web_user',
    # role-specific scopes
    'role_moderator',
    'role_administrator',
]


def scope_from_kwargs(
    *,
    read_prefs: bool = False,
    write_prefs: bool = False,
    write_api: bool = False,
    read_gpx: bool = False,
    write_gpx: bool = False,
    write_notes: bool = False,
    **_: bool,
) -> tuple[Scope, ...]:
    """
    Return the scopes from the given kwargs. Unsupported keys are ignored.

    >>> scope_from_kwargs(read_prefs=True, write_api=True, unknown=True)
    ('read_prefs', 'write_api')
    """
    result: list[Scope] = []
    if read_prefs:
        result.append('read_prefs')
    if write_prefs:
        result.append('write_prefs')
    if write_api:
        result.append('write_api')
    if read_gpx:
        result.append('read_gpx')
    if write_gpx:
        result.append('write_gpx')
    if write_notes:
        result.append('write_notes')
    return tuple(result)


def scope_from_str(s: str) -> tuple[Scope, ...]:
    """
    Get scopes from a string, where each scope is separated by a space. Only public scopes are resolved.

    >>> scope_from_str('read_prefs write_api skip_authorization')
    ('read_prefs', 'write_api')
    """
    return scope_from_kwargs(**{s: True for s in s.split() if s})


# noinspection PyTypeChecker
PUBLIC_SCOPES: frozenset[Scope] = frozenset(
    (
        'read_prefs',
        'write_prefs',
        'write_api',
        'read_gpx',
        'write_gpx',
        'write_notes',
    )
)
