from typing import ForwardRef, Union

import pytest

from app.services.admin_task_service import _format_annotation, _is_numeric


@pytest.mark.parametrize(
    ('annotation', 'expected'),
    [
        ('Foo', 'Foo'),
        (ForwardRef('Bar'), 'Bar'),
        (int | str, 'int | str'),
        (None, 'None'),
        (list[ForwardRef('T')], 'list[T]'),
        (dict[ForwardRef('Key'), list[int]], 'dict[Key, list[int]]'),
    ],
)
def test_format_annotation(annotation, expected):
    assert _format_annotation(annotation) == expected


@pytest.mark.parametrize(
    ('annotation', 'expected'),
    [
        (bool, False),
        (Union[int, 'float', None], True),
        ('int | str', False),
    ],
)
def test_is_numeric(annotation, expected):
    assert _is_numeric(annotation) is expected
