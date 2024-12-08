import pytest

from app.lib.rich_text import TextFormat, process_rich_text


@pytest.mark.parametrize(
    ('input', 'output'),
    [
        ('', '<p></p>'),
        (' ', '<p></p>'),
        ('1 line', '<p>1 line</p>'),
        ('2\nlines', '<p>2<br>lines</p>'),
        ('3\n\nlines', '<p>3<br><br>lines</p>'),
        ('[link text](.) **bold text**', '<p>[link text](.) **bold text**</p>'),
        ('<script>alert(1)</script>', '<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>'),
        ('&copy; 2024', '<p>&amp;copy; 2024</p>'),
        (
            'safe https://osm.org',
            '<p>safe <a href="https://osm.org" rel="noopener">https://osm.org</a></p>',
        ),
        (
            'unsafe https://example.com',
            '<p>unsafe <a href="https://example.com" rel="noopener nofollow">https://example.com</a></p>',
        ),
        (
            'upgrade safe http://example.osm.org',
            '<p>upgrade safe <a href="https://example.osm.org" rel="noopener">http://example.osm.org</a></p>',
        ),
        (
            '<a href="https://example.com">visit</a>',
            '<p>&lt;a href="<a href="https://example.com" rel="noopener nofollow">https://example.com</a>"&gt;visit&lt;/a&gt;</p>',
        ),
        (
            'support http://testtest.onion',
            '<p>support <a href="http://testtest.onion" rel="noopener nofollow">http://testtest.onion</a></p>',
        ),
        (
            'support http://testtest.dev',
            '<p>support <a href="http://testtest.dev" rel="noopener nofollow">http://testtest.dev</a></p>',
        ),
        (
            'mailto:testing@example.test',
            '<p><a href="mailto:testing@example.test" rel="noopener">mailto:testing@example.test</a></p>',
        ),
        ('tel:+1234567890', '<p>tel:+1234567890</p>'),
        ('ftp://example.com', '<p>ftp://example.com</p>'),
        ('//example.com', '<p>//example.com</p>'),
    ],
)
def test_plain_formatting(input: str, output: str):
    assert process_rich_text(input, TextFormat.plain) == output


@pytest.mark.parametrize(
    ('input', 'output'),
    [
        (
            '[link text](.) **bold text**',
            '<p><a href="." rel="noopener">link text</a> <strong>bold text</strong></p>',
        ),
        ('<script>alert(1)</script>', ''),
        ('&copy; 2024', '<p>© 2024</p>'),
        ('(c) 2024', '<p>© 2024</p>'),
        (
            'safe https://osm.org',
            '<p>safe <a href="https://osm.org" rel="noopener">https://osm.org</a></p>',
        ),
        (
            'unsafe http://example.com',
            '<p>unsafe <a href="http://example.com" rel="noopener nofollow">http://example.com</a></p>',
        ),
        (
            'upgrade safe http://example.osm.org',
            '<p>upgrade safe <a href="https://example.osm.org" rel="noopener">http://example.osm.org</a></p>',
        ),
    ],
)
def test_markdown_formatting(input: str, output: str):
    assert process_rich_text(input, TextFormat.markdown).strip() == output
