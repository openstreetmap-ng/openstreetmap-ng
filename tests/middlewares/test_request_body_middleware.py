import gzip
import zlib
from collections.abc import Callable
from urllib.parse import urlencode

import brotli
import orjson
import pytest
from httpx import AsyncClient
from zstandard import ZstdCompressor

from app.lib.xmltodict import XMLToDict


@pytest.mark.parametrize(
    ('encoding', 'compress'),
    [
        ('gzip', gzip.compress),
        ('deflate', zlib.compress),
        ('br', brotli.compress),
        ('zstd', ZstdCompressor().compress),
    ],
)
async def test_compressed_form(
    client: AsyncClient, changeset_id: int, encoding: str, compress: Callable[[bytes], bytes]
):
    client.headers['Authorization'] = 'User user1'

    text = f'{encoding}-compressed comment'
    content = compress(urlencode({'text': text}).encode())

    # create changeset comment
    r = await client.post(
        f'/api/0.6/changeset/{changeset_id}/comment',
        content=content,
        headers={
            'Content-Encoding': encoding,
            'Content-Type': 'application/x-www-form-urlencoded',
        },
    )
    assert r.is_success, r.text
    changeset: dict = XMLToDict.parse(r.content)['osm']['changeset']

    assert changeset['@id'] == changeset_id
    assert changeset['@comments_count'] == 1


@pytest.mark.parametrize(
    ('encoding', 'compress'),
    [
        ('gzip', gzip.compress),
        ('deflate', zlib.compress),
        ('br', brotli.compress),
        ('zstd', ZstdCompressor().compress),
    ],
)
async def test_compressed_json(client: AsyncClient, encoding: str, compress: Callable[[bytes], bytes]):
    client.headers['Authorization'] = 'User user1'

    text = f'{encoding}-compressed note'
    content = compress(orjson.dumps({'lon': 0, 'lat': 0, 'text': text}))

    # create note
    r = await client.post(
        '/api/0.6/notes.json',
        content=content,
        headers={'Content-Encoding': encoding},
    )
    assert r.is_success, r.text
    props: dict = r.json()['properties']
    comments: list[dict] = props['comments']

    assert props['status'] == 'open'
    assert len(comments) == 1

    assert comments[-1]['user'] == 'user1'
    assert comments[-1]['action'] == 'opened'
    assert comments[-1]['text'] == text
