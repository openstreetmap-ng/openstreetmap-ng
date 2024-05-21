import pytest

from app.lib.feature_icon import feature_icon


@pytest.mark.parametrize(
    ('type', 'tags', 'expected'),
    [
        ('way', {'crab': 'yes'}, ('crab_yes.webp', 'crab=yes')),
        ('node', {'non_existing_key': 'aaa'}, None),
    ],
)
def test_feature_icon(type, tags, expected):
    assert feature_icon(type, tags) == expected
