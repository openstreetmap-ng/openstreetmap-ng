import pytest

from app.validators.filename import _validate_filename  # noqa: PLC2701


@pytest.mark.parametrize(
    ('filename', 'expected'),
    [
        ('example.txt', 'example.txt'),
        ('hello_world.py', 'hello_world.py'),
        ('test123.jpg', 'test123.jpg'),
        ('hello world.txt', 'hello_world.txt'),
        ('special!@#$%^&*chars.txt', 'special_________chars.txt'),
        ('dashes-and_underscores.py', 'dashes_and_underscores.py'),
        ('path/to/file.txt', 'path_to_file.txt'),
        ('file:with:colons.txt', 'file_with_colons.txt'),
        ('file<with>brackets.txt', 'file_with_brackets.txt'),
        ('Mixed Case File.txt', 'Mixed_Case_File.txt'),
        ('file with spaces-and-dashes.txt', 'file_with_spaces_and_dashes.txt'),
        ('file_with_日本語.txt', 'file_with__.txt'),
        ('', ''),
        ('.hidden', '.hidden'),
        ('..', '..'),
        ('!@#$%^&*()', '__________'),
        ('file..with..dots', 'file..with..dots'),
    ],
)
def test_validate_filename(filename, expected):
    assert _validate_filename(filename) == expected
