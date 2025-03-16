import pytest

from app.lib.feature_name import features_names
from app.lib.translation import translation_context
from app.models.db.element import ElementInit
from app.models.element import ElementId, typed_element_id
from app.models.types import ChangesetId, LocaleCode


@pytest.mark.parametrize(
    ('tags', 'expected'),
    [
        # Basic name tag
        ({'name': 'Foo'}, 'Foo'),
        # Localized name takes precedence
        ({'name:pl': 'Foo po polsku', 'name': 'Foo'}, 'Foo po polsku'),
        # Fallback to default name when locale not available
        ({'name:de': 'Foo auf Deutsch', 'name': 'Foo'}, 'Foo'),
        # Reference number as fallback
        ({'ref': 'A123'}, 'A123'),
        # House name as fallback
        ({'addr:housename': 'Villa Maria'}, 'Villa Maria'),
        # House number + street as fallback
        ({'addr:housenumber': '42', 'addr:street': 'Main St'}, '42 Main St'),
        # House number + place as fallback
        ({'addr:housenumber': '42', 'addr:place': 'Downtown'}, '42 Downtown'),
        # No recognizable name tags
        ({'non_existing_key': 'aaa'}, None),
        # Empty tags
        ({}, None),
        # Multiple localized names - pick current locale
        ({'name:en': 'English Name', 'name:pl': 'Polish Name', 'name': 'Default Name'}, 'Polish Name'),
        # Prioritize current locale even in non-standard format
        ({'name:pl-PL': 'Polish Regional', 'name:pl': 'Polish Standard'}, 'Polish Standard'),
    ],
)
def test_features_names(tags: dict[str, str], expected: str | None):
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

    # Set translation context for test (using 'pl' that falls back to 'en')
    with translation_context(LocaleCode('pl')):
        result = features_names([element])[0]

    # Verify result
    assert result == expected, f"Expected name '{expected}', got '{result}'"


def test_features_names_multiple_elements():
    # Create elements using ElementInit structure
    element1: ElementInit = {
        'changeset_id': ChangesetId(1),
        'typed_id': typed_element_id('node', ElementId(1)),
        'version': 1,
        'visible': True,
        'tags': {'name': 'First Element'},
        'point': None,
        'members': None,
        'members_roles': None,
    }

    element2: ElementInit = {
        'changeset_id': ChangesetId(1),
        'typed_id': typed_element_id('way', ElementId(2)),
        'version': 1,
        'visible': True,
        'tags': {'ref': 'Second Element'},
        'point': None,
        'members': [],
        'members_roles': None,
    }

    # Get feature names for the elements
    with translation_context(LocaleCode('pl')):
        names = features_names([element1, element2])

    # Verify results
    assert len(names) == 2, 'Expected 2 results'
    assert names[0] == 'First Element'
    assert names[1] == 'Second Element'
