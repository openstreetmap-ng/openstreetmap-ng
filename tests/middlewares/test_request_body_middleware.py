import gzip
import zlib
from collections.abc import Callable
from functools import partial
from urllib.parse import urlencode

import brotli
import orjson
import pytest
from annotated_types import Len
from httpx import AsyncClient
from starlette import status
from zstandard import ZstdCompressor

from app.config import REQUEST_BODY_MAX_SIZE
from app.lib.xmltodict import XMLToDict
from app.models.types import ChangesetId
from tests.utils.assert_model import assert_model

# Lightweight compression levels for faster tests.
_ENCODING_COMPRESS: list[tuple[str, Callable[[bytes], bytes]]] = [
    ('gzip', partial(gzip.compress, compresslevel=1)),
    ('deflate', partial(zlib.compress, level=1)),
    ('br', partial(brotli.compress, quality=1)),
    ('zstd', ZstdCompressor(level=1).compress),
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
    text = f'{test_compressed_form.__qualname__}: {encoding}'
    content = urlencode({'text': text})

    # Execute request with compressed form data
    r = await client.post(
        f'/api/0.6/changeset/{changeset_id}/comment',
        content=compress(content.encode()),
        headers={
            'Content-Encoding': encoding,
            'Content-Type': 'application/x-www-form-urlencoded',
        },
    )

    # Verify response
    assert r.is_success, r.text

    changeset: dict = XMLToDict.parse(r.content)['osm']['changeset']  # type: ignore
    assert_model(
        changeset,
        {
            '@id': changeset_id,
            '@comments_count': 1,
        },
    )


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
    text = f'{test_compressed_json.__qualname__}: {encoding}'
    content = orjson.dumps({'lon': 0, 'lat': 0, 'text': text})

    # Execute request with compressed JSON
    r = await client.post(
        '/api/0.6/notes.json',
        content=compress(content),
        headers={
            'Content-Encoding': encoding,
            'Content-Type': 'application/json',
        },
    )

    # Verify response
    assert r.is_success, r.text

    props: dict = r.json()['properties']
    assert_model(props, {'status': 'open', 'comments': Len(1, 1)})
    assert_model(
        props['comments'][-1],
        {
            'user': 'user1',
            'action': 'opened',
            'text': text,
        },
    )


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
    content = XMLToDict.unparse({
        'osm': {
            'changeset': {
                'tag': [
                    {
                        '@k': 'created_by',
                        '@v': f'{test_compressed_xml.__qualname__}: {encoding}',
                    }
                ]
            }
        },
    })

    # Execute request with compressed XML
    r = await client.put(
        '/api/0.6/changeset/create',
        content=compress(content.encode()),
        headers={
            'Content-Encoding': encoding,
            'Content-Type': 'application/xml',
        },
    )

    # Verify response
    assert r.is_success, r.text
    assert int(r.text) > 0, 'Changeset id must be positive'


async def test_bad_compression_data(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    r = await client.post(
        '/api/0.6/notes.json',
        content=b'Bad compressed data',  # Intentionally corrupted data
        headers={
            'Content-Encoding': 'gzip',
            'Content-Type': 'application/json',
        },
    )

    # Verify response
    assert r.is_client_error, r.text


async def test_passthrough_unsupported_compression(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    # Setup test data
    text = 'unknown compression'
    content = orjson.dumps({'lon': 0, 'lat': 0, 'text': text})

    # Execute request with unsupported compression header
    r = await client.post(
        '/api/0.6/notes.json',
        content=content,
        headers={
            'Content-Encoding': 'unknown-format',
            'Content-Type': 'application/json',
        },
    )

    # Verify response
    assert r.is_success, r.text

    props: dict = r.json()['properties']
    assert_model(props, {'status': 'open', 'comments': Len(1, 1)})
    assert_model(
        props['comments'][-1],
        {
            'user': 'user1',
            'action': 'opened',
            'text': text,
        },
    )


@pytest.mark.extended
@pytest.mark.parametrize(
    ('encoding', 'compress'),
    _ENCODING_COMPRESS,
)
async def test_size_limit_after_decompression(
    client: AsyncClient,
    encoding: str,
    compress: Callable[[bytes], bytes],
):
    client.headers['Authorization'] = 'User user1'

    # Create data that's small when compressed but exceeds limits when decompressed
    content = compress(
        orjson.dumps({'lon': 0, 'lat': 0, 'text': 'A' * REQUEST_BODY_MAX_SIZE})
    )
    assert len(content) < REQUEST_BODY_MAX_SIZE, (
        'Compressed content must be under size limit'
    )

    # Execute request
    r = await client.post(
        '/api/0.6/notes.json',
        content=content,
        headers={
            'Content-Encoding': encoding,
            'Content-Type': 'application/json',
        },
    )

    # Verify response
    assert r.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, r.text
