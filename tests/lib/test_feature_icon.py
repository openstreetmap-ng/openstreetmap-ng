import pytest

from app.lib.feature_icon import FeatureIcon, features_icons
from app.models.db.element import ElementInit
from app.models.element import ElementId
from app.models.types import ChangesetId
from speedup import typed_element_id


@pytest.mark.parametrize(
    ('tags', 'expected'),
    [
        # Specific tag-value matches
        (
            {'shop': 'computer'},
            FeatureIcon(0, '_generated/shop_computer.webp', 'shop=computer'),
        ),
        # Generic fallback when no tag-value matches
        (
            {'shop': 'unspecified-shop-value'},
            FeatureIcon(0, '_generated/shop_convenience.webp', 'shop'),
        ),
        # Multiple matches - pick the less popular one
        (
            {'amenity': 'restaurant', 'crab': 'yes'},
            FeatureIcon(0, 'crab_yes.webp', 'crab=yes'),
        ),
        # No tag matches
        (
            {'non_existing_key': 'aaa'},
            None,
        ),
        # No type matches
        (
            {'barrier': 'wall'},
            None,
        ),
        # Empty tags
        (
            {},
            None,
        ),
        (
            None,
            None,
        ),
    ],
)
def test_features_icons(tags, expected: FeatureIcon | None):
    # Create element using ElementInit structure
    element: ElementInit = {
        'changeset_id': ChangesetId(1),
        'typed_id': typed_element_id('node', ElementId(1)),
        'version': 1,
        'visible': True,
        'tags': tags,
        'point': None,
        'members': None,
        'members_roles': None,
    }

    # Get feature icon for the element
    feature_icon = features_icons([element])[0]

    # Verify results
    if expected is None:
        assert feature_icon is None, 'Expected no icon, but got one'
    else:
        assert feature_icon is not None, 'Expected an icon, but got None'
        assert feature_icon.filename == expected.filename
        assert feature_icon.title == expected.title


def test_features_icons_mixed():
    # Create elements using ElementInit structure
    element1: ElementInit = {
        'changeset_id': ChangesetId(1),
        'typed_id': typed_element_id('node', ElementId(1)),
        'version': 1,
        'visible': True,
        'tags': {'amenity': 'restaurant'},
        'point': None,
        'members': None,
        'members_roles': None,
    }

    element2 = None

    # Get feature icons for the elements
    icons = features_icons([element1, element2])

    # Verify results
    assert len(icons) == 2, 'Expected 2 results'
    assert icons[0] is not None, 'First element must have an icon'
    assert icons[1] is None, 'Second element must be None'
