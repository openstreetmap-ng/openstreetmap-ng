import pytest

from app.lib.feature_name import features_names
from app.lib.translation import translation_context
from app.models.db.element import Element
from app.models.element import ElementId
from app.models.types import LocaleCode


@pytest.mark.parametrize(
    ('type', 'tags', 'expected'),
    [
        ('node', {'name': 'Foo'}, 'Foo'),
        ('way', {'name:pl': 'Foo', 'name': 'Bar'}, 'Foo'),
        ('node', {'ref': 'Foo'}, 'Foo'),
        ('way', {'non_existing_key': 'aaa'}, None),
        ('node', {}, None),
    ],
)
def test_features_names(type, tags, expected):
    element = Element(
        changeset_id=1,
        type=type,
        id=ElementId(1),
        version=1,
        visible=False,
        tags=tags,
        point=None,
        members=[],
    )
    with translation_context(LocaleCode('pl')):
        assert features_names((element,)) == (expected,)
