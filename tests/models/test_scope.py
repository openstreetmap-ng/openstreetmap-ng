from app.models.scope import PUBLIC_SCOPES, Scope


def test_from_kwargs():
    assert set(Scope.from_kwargs(read_prefs=True, write_prefs=True)) == {Scope.read_prefs, Scope.write_prefs}


def test_from_str():
    assert set(Scope.from_str('read_prefs write_api skip_authorization')) == {Scope.read_prefs, Scope.write_api}


def test_from_str_public():
    assert set(Scope.from_str(' '.join(s.value for s in Scope))) == set(PUBLIC_SCOPES)
