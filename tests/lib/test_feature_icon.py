from typing import NamedTuple

from app.lib.feature_icon import feature_icon
from app.models.element_type import ElementType


def test_feature_icon():
    class DummyElement(NamedTuple):
        type: ElementType
        tags: dict[str, str]

    assert feature_icon(
        DummyElement(
            type='way',
            tags={'aeroway': 'terminal'},
        )
    ) == ('aeroway_terminal.webp', 'aeroway=terminal')

    assert feature_icon(
        DummyElement(
            type='node',
            tags={'source': 'bing'},
        )
    ) == (None, None)
