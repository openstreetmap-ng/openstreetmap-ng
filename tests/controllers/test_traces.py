from base64 import urlsafe_b64decode
from pathlib import Path

import pytest
from httpx import AsyncClient
from re2 import search

from app.models.proto.trace_pb2 import (
    DetailsPage,
    EditPage,
    IndexPage,
    Metadata,
    UploadPage,
    UploadRequest,
    UploadResponse,
    Visibility,
)
from app.models.proto.trace_types import Visibility as TraceVisibility

_GPX_BYTES = Path('tests/data/8473730.gpx').read_bytes()


def _trace_state(html: str, message_cls):
    match = search(r'data-state="([^"]*)"', html)
    assert match is not None
    return message_cls.FromString(urlsafe_b64decode(match.group(1) + '=='))


async def _upload_trace(
    client: AsyncClient,
    *,
    description: str,
    visibility: TraceVisibility,
):
    r = await client.post(
        '/rpc/trace.Service/Upload',
        headers={'Content-Type': 'application/proto'},
        content=UploadRequest(
            file=_GPX_BYTES,
            metadata=Metadata(
                name=f'{description}.gpx',
                description=description,
                tags=['tag1', 'tag2'],
                visibility=Visibility.Value(visibility),
            ),
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    return int(UploadResponse.FromString(r.content).id)


@pytest.mark.parametrize(
    ('path', 'expected_redirect', 'auth'),
    [
        ('/user/Zaczero/traces/152', '/trace/152', None),
        ('/traces/new', '/trace/upload', None),
        ('/traces/mine', '/user/user1/traces', 'User user1'),
        ('/traces/mine/tag/hiking', '/user/user1/traces/tag/hiking', 'User user1'),
    ],
)
async def test_trace_redirects(
    client: AsyncClient,
    path: str,
    expected_redirect: str,
    auth: str | None,
):
    if auth is not None:
        client.headers['Authorization'] = auth

    r = await client.get(path, follow_redirects=False)
    assert r.is_redirect, r.text
    assert r.headers['Location'] == expected_redirect


async def test_trace_controller_flow(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    trace_id = await _upload_trace(
        client,
        description='test_trace_controller_flow',
        visibility='public',
    )

    r = await client.get('/user/definitely-missing/traces')
    assert r.status_code == 404, r.text

    r = await client.get('/traces')
    assert r.is_success, r.text
    state = _trace_state(r.text, IndexPage)
    assert state.WhichOneof('owner') is None

    r = await client.get('/user/user1/traces')
    assert r.is_success, r.text
    state = _trace_state(r.text, IndexPage)
    assert state.WhichOneof('owner') == 'self'

    client.headers.pop('Authorization')

    r = await client.get('/user/user1/traces')
    assert r.is_success, r.text
    state = _trace_state(r.text, IndexPage)
    assert state.WhichOneof('owner') == 'profile'
    assert state.profile.display_name == 'user1'

    client.headers['Authorization'] = 'User user1'

    r = await client.get('/trace/upload')
    assert r.is_success, r.text
    _trace_state(r.text, UploadPage)

    r = await client.get(f'/trace/{trace_id}')
    assert r.is_success, r.text
    details = _trace_state(r.text, DetailsPage)
    assert details.trace.id == trace_id
    assert details.trace.user.display_name == 'user1'
    assert details.trace.metadata.description == 'test_trace_controller_flow'
    assert details.trace.line

    r = await client.get(f'/trace/{trace_id}/edit')
    assert r.is_success, r.text
    edit = _trace_state(r.text, EditPage)
    assert edit.trace.id == trace_id
    assert edit.trace.metadata.name == 'test_trace_controller_flow.gpx'
    assert edit.trace.metadata.description == 'test_trace_controller_flow'
    assert edit.trace.line

    client.headers['Authorization'] = 'User user2'
    r = await client.get(f'/trace/{trace_id}/edit')
    assert r.status_code == 403, r.text
