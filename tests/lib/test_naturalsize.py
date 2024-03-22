from app.lib.naturalsize import naturalsize


def test_naturalsize():
    assert naturalsize(10000) == '9.77 KiB'
    assert naturalsize(1024) == '1.00 KiB'
    assert naturalsize(1023) == '1023 B'
