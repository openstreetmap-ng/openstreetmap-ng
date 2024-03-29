from app.lib.feature_name import feature_name, feature_prefix
from app.lib.translation import translation_context


def test_feature_prefix():
    with translation_context('en'):
        assert (
            feature_prefix(
                'way',
                {
                    'boundary': 'administrative',
                    'admin_level': '2',
                },
            )
            == 'Country Boundary'
        )

        assert feature_prefix('node', {'amenity': 'restaurant'}) == 'Restaurant'
        assert feature_prefix('node', {}) == 'Node'


def test_feature_name():
    with translation_context('pl'):
        assert feature_name({'name': 'Foo'}) == 'Foo'
        assert feature_name({'name:pl': 'Foo', 'name': 'Bar'}) == 'Foo'
        assert feature_name({'non_existing_key': 'aaa'}) is None
        assert feature_name({}) is None
