from app.models.scope import PUBLIC_SCOPES, scope_from_kwargs, scope_from_str


def test_from_kwargs():
    assert set(scope_from_kwargs(read_prefs=True, write_prefs=True)) == {'read_prefs', 'write_prefs'}


def test_from_str():
    assert set(scope_from_str('read_prefs write_api skip_authorization')) == {'read_prefs', 'write_api'}


def test_from_str_public():
    assert set(scope_from_str(' '.join(PUBLIC_SCOPES))) == set(PUBLIC_SCOPES)
