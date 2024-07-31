from app.lib.updating_cached_property import updating_cached_property


class _Dummy:
    a: int = 0
    call_count: int = 0

    @updating_cached_property('a')
    def a_plus_one(self) -> int:
        self.call_count += 1
        return self.a + 1


def test_updating_cached_property():
    d = _Dummy()
    d.a = 1
    assert d.a_plus_one == 2
    assert d.call_count == 1

    d.a = 1
    assert d.a_plus_one == 2
    assert d.call_count == 1

    d.a = 2
    assert d.a_plus_one == 3
    assert d.call_count == 2


def test_updating_cached_property_cache_pollution():
    d = _Dummy()
    d.a = 1
    assert d.a_plus_one == 2
    assert d.call_count == 1

    d = _Dummy()
    d.a = 1
    assert d.a_plus_one == 2
    assert d.call_count == 1

    d = _Dummy()
    d.a = 2
    assert d.a_plus_one == 3
    assert d.call_count == 1
