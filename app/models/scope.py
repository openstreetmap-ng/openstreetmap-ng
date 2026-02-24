from collections.abc import Iterable
from typing import Literal, get_args

from app.models.proto.shared_pb2 import Scope as ProtoScope

type PublicScope = Literal[
    'read_prefs',
    'write_prefs',
    'write_api',
    'read_gpx',
    'write_gpx',
    'write_notes',
]

PUBLIC_SCOPES = frozenset[PublicScope](get_args(PublicScope.__value__))

type Scope = (
    PublicScope
    | Literal[
        # additional scopes
        'web_user',
        'read_email',
        'skip_authorization',
        # role-specific scopes
        'role_moderator',
        'role_administrator',
    ]
)


def scope_from_kwargs(
    *,
    read_prefs: bool = False,
    write_prefs: bool = False,
    write_api: bool = False,
    read_gpx: bool = False,
    write_gpx: bool = False,
    write_notes: bool = False,
    **_: bool,
):
    """
    Return the scopes from the given kwargs. Unsupported keys are ignored.

    >>> scope_from_kwargs(read_prefs=True, write_api=True, unknown=True)
    frozenset({'read_prefs', 'write_api'})
    """
    result: list[PublicScope] = []
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
    return frozenset(result)


def scope_from_str(s: str):
    """
    Get scopes from a string, where each scope is separated by a space. Only public scopes are resolved.

    >>> scope_from_str('read_prefs write_api skip_authorization')
    frozenset({'read_prefs', 'write_api'})
    """
    return scope_from_kwargs(**dict.fromkeys((s for s in s.split() if s), True))


def scope_from_proto(scopes: Iterable[int]):
    """
    Get public scopes from a repeated proto enum field.

    >>> scope_from_proto([ProtoScope.read_prefs, ProtoScope.write_api, ProtoScope.web_user])
    frozenset({'read_prefs', 'write_api'})
    """
    return scope_from_kwargs(
        **dict.fromkeys((ProtoScope.Name(scope) for scope in scopes), True)
    )
