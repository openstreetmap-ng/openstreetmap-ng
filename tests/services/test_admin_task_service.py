from typing import ForwardRef

import pytest

from app.services.admin_task_service import _format_annotation


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
