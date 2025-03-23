import pytest

from app.lib.feature_prefix import features_prefixes
from app.lib.translation import translation_context
from app.models.db.element import ElementInit
from app.models.element import ElementId, typed_element_id
from app.models.types import ChangesetId, LocaleCode


@pytest.mark.parametrize(
    ('type', 'tags', 'expected'),
    [
        # Administrative boundaries with different levels
        (
            'way',
            {'boundary': 'administrative', 'admin_level': '2'},
            'Country Boundary',
        ),
        (
            'relation',
            {'boundary': 'administrative', 'admin_level': '8'},
            'City Boundary',
        ),
        # Common feature types
        (
            'node',
            {'amenity': 'restaurant'},
            'Restaurant',
        ),
        (
            'node',
            {'shop': 'supermarket'},
            'Supermarket',
        ),
        (
            'way',
            {'highway': 'residential'},
            'Residential Road',
        ),
        (
            'node',
            {'tourism': 'hotel'},
            'Hotel',
        ),
        # Fallback to auto-capitalized value when key is recognized but value isn't
        (
            'node',
            {'amenity': 'unusual_feature'},
            'Unusual feature',
        ),
        # Generic type prefixes for elements without recognized tags
        (
            'node',
            {},
            'Node',
        ),
        (
            'node',
            None,
            'Node',
        ),
        (
            'way',
            {},
            'Way',
        ),
        (
            'relation',
            {},
            'Relation',
        ),
    ],
)
def test_features_prefixes(type, tags, expected):
    # Create element using ElementInit structure
    element: ElementInit = {
        'changeset_id': ChangesetId(1),
        'typed_id': typed_element_id(type, ElementId(1)),
        'version': 1,
        'visible': True,
        'tags': tags,
        'point': None,
        'members': None,
        'members_roles': None,
    }

    # Set translation context for test
    with translation_context(LocaleCode('en')):
        result = features_prefixes([element])[0]

    # Verify result
    assert result == expected, f'Expected prefix "{expected}", got "{result}"'


def test_features_prefixes_with_none():
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

    # Get feature prefixes for the elements
    with translation_context(LocaleCode('en')):
        prefixes = features_prefixes([element1, element2])

    # Verify results
    assert len(prefixes) == 2, 'Expected 2 results'
    assert prefixes[0] == 'Restaurant', 'First element must have "Restaurant" prefix'
    assert prefixes[1] is None, 'Second element must be None'
