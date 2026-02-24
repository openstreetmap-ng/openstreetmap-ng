from app.models.proto.shared_pb2 import Scope
from app.models.scope import (
    PUBLIC_SCOPES,
    scope_from_kwargs,
    scope_from_proto,
    scope_from_str,
)


def test_from_kwargs():
    assert scope_from_kwargs(read_prefs=True, write_prefs=True) == {
        'read_prefs',
        'write_prefs',
    }


def test_from_str():
    assert scope_from_str('read_prefs write_api skip_authorization') == {
        'read_prefs',
        'write_api',
    }


def test_from_str_public():
    assert scope_from_str(' '.join(PUBLIC_SCOPES)) == PUBLIC_SCOPES


def test_from_proto():
    assert scope_from_proto([Scope.read_prefs, Scope.write_api, Scope.web_user]) == {
        'read_prefs',
        'write_api',
    }
