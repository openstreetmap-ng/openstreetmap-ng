from html.parser import HTMLParser

from httpx import AsyncClient


class _Page(HTMLParser):
    def __init__(self, html: str):
        super().__init__()
        self.cards = 0
        self.forms = []
        self.selected = []
        self.images = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'article':
            self.cards += 1
        elif tag == 'form':
            self.forms.append(attrs)
        elif tag == 'option' and 'selected' in attrs:
            self.selected.append(attrs['value'])
        elif tag == 'img':
            self.images.append(attrs.get('src', ''))


async def test_software_directory(client: AsyncClient):
    response = await client.get('/software')
    assert response.is_success, response.text
    page = _Page(response.text)
    assert page.cards == 5
    assert any(
        form.get('action') == '/software' and form.get('method', '').lower() == 'get'
        for form in page.forms
    )
    assert '5 applications' in response.text
    assert 'software.' not in response.text


async def test_software_directory_combined_filters(client: AsyncClient):
    response = await client.get(
        '/software?platform=windows&category=tiles&license=proprietary&status=maintained'
    )
    assert response.is_success, response.text
    page = _Page(response.text)
    assert page.cards == 1
    assert set(page.selected) == {'windows', 'tiles', 'proprietary', 'maintained'}
    assert 'MapTiler Engine' in response.text
    assert 'Organic Maps' not in response.text
    assert '/static/img/software/maptiler.svg' in page.images
    assert '1 application' in response.text


async def test_software_directory_empty_and_invalid(client: AsyncClient):
    empty = await client.get('/software?platform=android&license=proprietary')
    assert empty.is_success, empty.text
    assert _Page(empty.text).cards == 0
    assert 'No applications match' in empty.text
    assert '0 applications' in empty.text

    invalid = await client.get('/software?platform=unknown&license=unknown')
    assert invalid.is_success, invalid.text
    assert _Page(invalid.text).cards == 5
    assert _Page(invalid.text).selected == []
