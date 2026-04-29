from pathlib import Path

from httpx import AsyncClient

from app.models.proto.trace_pb2 import (
    DeleteRequest,
    GetPageRequest,
    GetPageResponse,
    Metadata,
    UpdateRequest,
    UploadRequest,
    UploadResponse,
    Visibility,
)
from app.models.proto.trace_types import Visibility as VisibilityType
from app.models.types import DisplayName
from app.queries.user_query import UserQuery

_GPX_BYTES = Path('tests/data/8473730.gpx').read_bytes()


async def _upload_trace(
    client: AsyncClient,
    *,
    name: str,
    description: str,
    tags: list[str],
    visibility: VisibilityType,
):
    r = await client.post(
        '/rpc/trace.Service/Upload',
        headers={'Content-Type': 'application/proto'},
        content=UploadRequest(
            file=_GPX_BYTES,
            metadata=Metadata(
                name=name,
                description=description,
                tags=tags,
                visibility=Visibility.Value(visibility),
            ),
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    return int(UploadResponse.FromString(r.content).id)


async def test_trace_lifecycle(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    public_trace_id = await _upload_trace(
        client,
        name='public-trace.gpx',
        description='Public RPC trace',
        tags=['rpc-public'],
        visibility='public',
    )
    private_trace_id = await _upload_trace(
        client,
        name='private-trace.gpx',
        description='Private RPC trace',
        tags=['rpc-private'],
        visibility='private',
    )

    client.headers.pop('Authorization')

    r = await client.post(
        '/rpc/trace.Service/GetPage',
        headers={'Content-Type': 'application/proto'},
        content=GetPageRequest().SerializeToString(),
    )
    assert r.is_success, r.text

    response = GetPageResponse.FromString(r.content)
    assert any(trace.summary.id == public_trace_id for trace in response.traces)
    assert all(trace.summary.id != private_trace_id for trace in response.traces)
    public_trace = next(
        trace for trace in response.traces if trace.summary.id == public_trace_id
    )
    assert public_trace.summary.preview_line
    assert public_trace.user.display_name == 'user1'

    client.headers['Authorization'] = 'User user1'
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user is not None

    r = await client.post(
        '/rpc/trace.Service/GetPage',
        headers={'Content-Type': 'application/proto'},
        content=GetPageRequest(user_id=user['id']).SerializeToString(),
    )
    assert r.is_success, r.text

    response = GetPageResponse.FromString(r.content)
    assert any(trace.summary.id == private_trace_id for trace in response.traces)

    r = await client.post(
        '/rpc/trace.Service/Update',
        headers={'Content-Type': 'application/proto'},
        content=UpdateRequest(
            id=private_trace_id,
            metadata=Metadata(
                name='updated-private-trace.gpx',
                description='Updated RPC trace',
                tags=['rpc-updated'],
                visibility=Visibility.public,
            ),
        ).SerializeToString(),
    )
    assert r.is_success, r.text

    client.headers.pop('Authorization')

    r = await client.post(
        '/rpc/trace.Service/GetPage',
        headers={'Content-Type': 'application/proto'},
        content=GetPageRequest(tag='rpc-updated').SerializeToString(),
    )
    assert r.is_success, r.text

    response = GetPageResponse.FromString(r.content)
    updated_trace = next(
        trace for trace in response.traces if trace.summary.id == private_trace_id
    )
    assert updated_trace.name == 'updated_private_trace.gpx'
    assert updated_trace.summary.description == 'Updated RPC trace'
    assert updated_trace.summary.visibility == Visibility.public

    client.headers['Authorization'] = 'User user1'

    r = await client.post(
        '/rpc/trace.Service/Delete',
        headers={'Content-Type': 'application/proto'},
        content=DeleteRequest(id=private_trace_id).SerializeToString(),
    )
    assert r.is_success, r.text

    r = await client.post(
        '/rpc/trace.Service/GetPage',
        headers={'Content-Type': 'application/proto'},
        content=GetPageRequest(user_id=user['id']).SerializeToString(),
    )
    assert r.is_success, r.text

    response = GetPageResponse.FromString(r.content)
    assert all(trace.summary.id != private_trace_id for trace in response.traces)
