import gzip
import zlib
from collections.abc import Callable
from functools import partial
from urllib.parse import urlencode

import brotli
import orjson
import pytest
from httpx import AsyncClient
from starlette import status
from zstandard import ZstdCompressor

from app.lib.xmltodict import XMLToDict
from app.limits import REQUEST_BODY_MAX_SIZE
from app.models.types import ChangesetId

# Prefer using lightweight compression levels for faster tests.
_ENCODING_COMPRESS: list[tuple[str, Callable[[bytes], bytes]]] = [
    ('gzip', partial(gzip.compress, compresslevel=0)),
    ('deflate', partial(zlib.compress, level=0)),
    ('br', partial(brotli.compress, quality=0)),
    ('zstd', ZstdCompressor(level=0).compress),
]


@pytest.mark.parametrize(
    ('encoding', 'compress'),
    _ENCODING_COMPRESS,
)
async def test_compressed_form(
    client: AsyncClient,
    changeset_id: ChangesetId,
    encoding: str,
    compress: Callable[[bytes], bytes],
):
    client.headers['Authorization'] = 'User user1'

    # Setup test data
    text = f'{encoding}-compressed form'

    # Execute request with compressed form data
    r = await client.post(
        f'/api/0.6/changeset/{changeset_id}/comment',
        content=compress(urlencode({'text': text}).encode()),
        headers={
            'Content-Encoding': encoding,
            'Content-Type': 'application/x-www-form-urlencoded',
        },
    )

    # Verify response
    assert r.is_success, f'Request must succeed, got {r.status_code}: {r.text}'

    changeset: dict = XMLToDict.parse(r.content)['osm']['changeset']  # type: ignore
    assert changeset['@id'] == changeset_id, 'Changeset id must match'
    assert changeset['@comments_count'] == 1, 'Comment must be added'


@pytest.mark.parametrize(
    ('encoding', 'compress'),
    _ENCODING_COMPRESS,
)
async def test_compressed_json(
    client: AsyncClient,
    encoding: str,
    compress: Callable[[bytes], bytes],
):
    client.headers['Authorization'] = 'User user1'

    # Setup test data
    text = f'{encoding}-compressed json'

    # Execute request with compressed JSON
    r = await client.post(
        '/api/0.6/notes.json',
        content=compress(orjson.dumps({'lon': 0, 'lat': 0, 'text': text})),
        headers={
            'Content-Encoding': encoding,
            'Content-Type': 'application/json',
        },
    )

    # Verify response
    assert r.is_success, f'Request must succeed, got {r.status_code}: {r.text}'

    props: dict = r.json()['properties']
    comments: list[dict] = props['comments']
    assert props['status'] == 'open', 'Note must be created with open status'
    assert len(comments) == 1, 'Note must have exactly one comment'
    assert comments[-1]['user'] == 'user1', 'Comment user must be correct'
    assert comments[-1]['action'] == 'opened', "Comment action must be 'opened'"
    assert comments[-1]['text'] == text, 'Comment text must match input'


@pytest.mark.parametrize(
    ('encoding', 'compress'),
    _ENCODING_COMPRESS,
)
async def test_compressed_xml(
    client: AsyncClient,
    encoding: str,
    compress: Callable[[bytes], bytes],
):
    client.headers['Authorization'] = 'User user1'

    # Setup test data
    xml_content = XMLToDict.unparse({
        'osm': {'changeset': {'tag': [{'@k': 'created_by', '@v': f'{encoding}-compressed xml'}]}},
    })

    # Execute request with compressed XML
    r = await client.put(
        '/api/0.6/changeset/create',
        content=compress(xml_content.encode()),
        headers={
            'Content-Encoding': encoding,
            'Content-Type': 'application/xml',
        },
    )

    # Verify response
    assert r.is_success, f'Request must succeed, got {r.status_code}: {r.text}'
    assert int(r.text) > 0, 'Changeset id must be positive'


async def test_bad_compression_data(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # Execute request with bad compression
    r = await client.post(
        '/api/0.6/notes.json',
        content=b'Bad compressed data',
        headers={
            'Content-Encoding': 'gzip',
            'Content-Type': 'application/json',
        },
    )

    # Verify response
    assert r.is_client_error, f'Request must result in client error, got {r.status_code}: {r.text}'


async def test_passthrough_unsupported_compression(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # Setup test with unsupported compression
    text = 'test note with unknown compression'
    content = orjson.dumps({'lon': 0, 'lat': 0, 'text': text})

    # Execute request with unknown compression type
    r = await client.post(
        '/api/0.6/notes.json',
        content=content,
        headers={
            'Content-Encoding': 'unknown-format',
            'Content-Type': 'application/json',
        },
    )

    # Verify response
    assert r.is_success, f'Request must succeed, got {r.status_code}: {r.text}'


@pytest.mark.extended
async def test_size_limit_after_decompression(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # Setup large compressible payload
    large_text = 'a' * REQUEST_BODY_MAX_SIZE
    content = gzip.compress(orjson.dumps({'lon': 0, 'lat': 0, 'text': large_text}), compresslevel=0)

    # Verify compressed size is under limit but decompressed exceeds
    assert len(content) < REQUEST_BODY_MAX_SIZE, 'Compressed content must be under size limit'

    # Execute request
    r = await client.post(
        '/api/0.6/notes.json',
        content=content,
        headers={
            'Content-Encoding': 'gzip',
            'Content-Type': 'application/json',
        },
    )

    # Verify response
    assert r.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, (
        f'Request must result in 413 error, got {r.status_code}: {r.text}'
    )
