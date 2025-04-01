import pytest

from app.config import TAGS_KEY_MAX_LENGTH, TAGS_LIMIT
from app.validators.tags import TagsValidator


@pytest.mark.parametrize(
    ('tags', 'valid'),
    [
        ({}, True),
        ({'k': 'v'}, True),
        ({'safe_key': 'safe_value'}, True),
        ({'key-with.special_chars': 'value-with.special_chars'}, True),
        # Count limit
        ({f'key{i}': 'value' for i in range(TAGS_LIMIT)}, True),  # Exact limit of tags
        ({f'key{i}': 'value' for i in range(TAGS_LIMIT + 1)}, False),  # Exceeds tags count
        # Key length
        ({'': 'value'}, False),  # Empty key
        ({('k' * TAGS_KEY_MAX_LENGTH): 'value'}, True),  # Maximum key length
        ({('k' * (TAGS_KEY_MAX_LENGTH + 1)): 'value'}, False),  # Key too long
        # Value length
        ({'key': ''}, False),  # Empty value
        ({'key': 'v' * 255}, True),  # Maximum value length
        ({'key': 'v' * 256}, False),  # Value too long
        # Invalid XML characters in key
        ({f'key_with_null_char{chr(0)}': 'value'}, False),
        ({f'key_with_control_char{chr(1)}': 'value'}, False),
        ({f'key_with_bad_xml{chr(0x0B)}': 'value'}, False),
        # Invalid XML characters in value
        ({'key': f'value_with_null_char{chr(0)}'}, False),
        ({'key': f'value_with_control_char{chr(1)}'}, False),
        ({'key': f'value_with_bad_xml{chr(0x0B)}'}, False),
    ],
)
def test_tags_validation(tags, valid):
    try:
        validated = TagsValidator.validate_python(tags)
        assert valid
        assert validated == tags
    except Exception:
        assert not valid
