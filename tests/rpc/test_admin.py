from httpx import AsyncClient

from app.models.proto.admin_users_pb2 import Filters, ListRequest


async def test_list_admin_users_requires_admin(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    r = await client.post(
        '/rpc/admin_users.Service/List',
        headers={'Content-Type': 'application/proto'},
        content=ListRequest(filters=Filters(sort='created_desc')).SerializeToString(),
    )

    assert r.status_code == 403, r.text
