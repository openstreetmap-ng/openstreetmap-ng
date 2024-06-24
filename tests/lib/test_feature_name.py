import pytest

from app.lib.feature_name import feature_name, features_prefixes
from app.lib.translation import translation_context
from app.models.db.element import Element


@pytest.mark.parametrize(
    ('tags', 'expected'),
    [
        ({'name': 'Foo'}, 'Foo'),
        ({'name:pl': 'Foo', 'name': 'Bar'}, 'Foo'),
        ({'ref': 'Foo'}, 'Foo'),
        ({'non_existing_key': 'aaa'}, None),
        ({}, None),
    ],
)
def test_feature_name(tags, expected):
    with translation_context('pl'):
        assert feature_name(tags) == expected


@pytest.mark.parametrize(
    ('type', 'tags', 'expected'),
    [
        ('way', {'boundary': 'administrative', 'admin_level': '2'}, 'Country Boundary'),
        ('node', {'amenity': 'restaurant'}, 'Restaurant'),
        ('node', {}, 'Node'),
    ],
)
def test_features_prefixes(type, tags, expected):
    element = Element(
        changeset_id=1,
        type=type,
        id=1,
        version=1,
        visible=False,
        tags=tags,
        point=None,
        members=[],
    )
    with translation_context('en'):
        assert features_prefixes((element,)) == (expected,)
