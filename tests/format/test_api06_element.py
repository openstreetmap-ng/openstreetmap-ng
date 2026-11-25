import pytest

from app.format import Format06


def test_decode_node_rejects_null_island():
    with pytest.raises(ValueError, match='null island'):
        Format06.decode_elements([
            (
                'node',
                {
                    '@id': -1,
                    '@changeset': 1,
                    '@version': 0,
                    '@lon': 0,
                    '@lat': 0,
                },
            )
        ])


def test_decode_hidden_node_allows_null_island():
    elements = Format06.decode_elements([
        (
            'node',
            {
                '@id': 1,
                '@changeset': 1,
                '@version': 1,
                '@visible': False,
                '@lon': 0,
                '@lat': 0,
            },
        )
    ])

    assert elements[0]['point'] is None
