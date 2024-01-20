import pytest

from app.lib.tag_format import TagFormatTuple, tag_format
from app.models.tag_format import TagFormat


# TODO: test wikipedia, wikidata, wikimedia_commons
@pytest.mark.parametrize(
    ('input', 'output'),
    [
        (
            ('colour', ''),
            (),
        ),
        (
            ('colour', '#ff0000;invalid;aliceblue'),
            (
                TagFormatTuple(TagFormat.color, '#ff0000', '#ff0000'),
                TagFormatTuple(TagFormat.default, 'invalid', 'invalid'),
                TagFormatTuple(TagFormat.color, 'aliceblue', 'aliceblue'),
            ),
        ),
        (
            ('colour', '#ff00001; #ff0000'),
            (
                TagFormatTuple(TagFormat.default, '#ff00001', '#ff00001'),
                TagFormatTuple(TagFormat.default, ' #ff0000', ' #ff0000'),
            ),
        ),
        (
            ('email', 'support@openstreetmap.org;example@example.com'),
            (
                TagFormatTuple(TagFormat.email, 'support@openstreetmap.org', 'mailto:support@openstreetmap.org'),
                TagFormatTuple(TagFormat.email, 'example@example.com', 'mailto:example@example.com'),
            ),
        ),
        (
            ('email', 'invalid email address'),
            (TagFormatTuple(TagFormat.default, 'invalid email address', 'invalid email address'),),
        ),
        (
            ('phone', '+1-234-567-8901;+7925805204786492'),
            (
                TagFormatTuple(TagFormat.phone, '+1-234-567-8901', 'tel:+12345678901'),
                TagFormatTuple(TagFormat.default, '+7925805204786492', '+7925805204786492'),
            ),
        ),
        (
            ('url', 'https://www.openstreetmap.org;ftp://www.openstreetmap.org'),
            (
                TagFormatTuple(TagFormat.url, 'https://www.openstreetmap.org', 'https://www.openstreetmap.org'),
                TagFormatTuple(TagFormat.default, 'ftp://www.openstreetmap.org', 'ftp://www.openstreetmap.org'),
            ),
        ),
    ],
)
def test_tag_format(input, output):
    assert tag_format(*input) == output
