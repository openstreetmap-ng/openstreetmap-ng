import pytest

from app.lib.feature_name import feature_name
from app.lib.translation import translation_context
from app.models.types import LocaleCode


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
    with translation_context(LocaleCode('pl')):
        assert feature_name(tags) == expected
