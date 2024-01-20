from app.lib.updating_cached_property import updating_cached_property


def test_updating_cached_property():
    class Dummy:
        a: int
        call_count: int = 0

        @updating_cached_property('a')
        def a_plus_one(self) -> int:
            self.call_count += 1
            return self.a + 1

    d = Dummy()
    d.a = 1
    assert d.a_plus_one == 2
    assert d.call_count == 1

    d.a = 1
    assert d.a_plus_one == 2
    assert d.call_count == 1

    d.a = 2
    assert d.a_plus_one == 3
    assert d.call_count == 2
