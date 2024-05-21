import pytest

from app.lib.feature_name import feature_name, feature_prefix
from app.lib.translation import translation_context


@pytest.mark.parametrize(
    ('type', 'tags', 'output'),
    [
        ('way', {'boundary': 'administrative', 'admin_level': '2'}, 'Country Boundary'),
        ('node', {'amenity': 'restaurant'}, 'Restaurant'),
        ('node', {}, 'Node'),
    ],
)
def test_feature_prefix(type, tags, output):
    with translation_context('en'):
        assert feature_prefix(type, tags) == output


@pytest.mark.parametrize(
    ('tags', 'output'),
    [
        ({'name': 'Foo'}, 'Foo'),
        ({'name:pl': 'Foo', 'name': 'Bar'}, 'Foo'),
        ({'ref': 'Foo'}, 'Foo'),
        ({'non_existing_key': 'aaa'}, None),
        ({}, None),
    ],
)
def test_feature_name(tags, output):
    with translation_context('pl'):
        assert feature_name(tags) == output
