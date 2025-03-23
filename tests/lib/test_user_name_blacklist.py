import pytest

from app.lib.user_name_blacklist import is_user_name_blacklisted


@pytest.mark.parametrize(
    ('display_name', 'blacklisted'),
    [
        ('New', True),
        ('new', True),
        (' new ', True),
        ('N e w', False),
        ('NorthCrab', False),
    ],
)
def test_is_user_name_blacklisted(display_name, blacklisted):
    assert is_user_name_blacklisted(display_name) == blacklisted
