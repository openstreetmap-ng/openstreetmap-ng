import pytest

from app.lib.feature_icon import FeatureIcon, features_icons
from app.models.db.element import Element
from app.models.element import ElementId


@pytest.mark.parametrize(
    ('type', 'tags', 'expected'),
    [
        (
            'way',
            {'crab': 'yes'},
            FeatureIcon(0, 'crab_yes.webp', 'crab=yes'),
        ),
        (
            'node',
            {'non_existing_key': 'aaa'},
            None,
        ),
    ],
)
def test_features_icons(type, tags, expected: FeatureIcon | None):
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
    feature_icon = features_icons((element,))[0]
    if expected is None:
        assert feature_icon is None
    else:
        assert feature_icon is not None
        assert feature_icon.filename == expected.filename
        assert feature_icon.title == expected.title
