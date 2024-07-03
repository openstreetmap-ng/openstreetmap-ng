from app.lib.lru_cache import LRUCache


def test_lru_cache_maxsize():
    cache: LRUCache[str, int] = LRUCache(2)
    cache['1'] = 1
    cache['2'] = 2
    cache['3'] = 3
    assert cache.get('1') is None
    assert cache.get('2') == 2
    assert cache.get('3') == 3

    cache.get('2')
    cache['4'] = 4
    assert cache.get('2') == 2
    assert cache.get('3') is None
    assert cache.get('4') == 4


def test_lru_cache_move_to_end():
    cache: LRUCache[str, int] = LRUCache(2)
    cache['1'] = 1
    cache['2'] = 2
    cache['3'] = 3
    assert cache.get('1') is None
    assert cache.get('2') == 2
    assert cache.get('3') == 3

    cache['2'] = 2
    cache['4'] = 4
    assert cache.get('2') == 2
    assert cache.get('3') is None
    assert cache.get('4') == 4
