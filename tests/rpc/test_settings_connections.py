from httpx import AsyncClient

from app.db import db
from app.models.proto.settings_connections_pb2 import RemoveRequest
from app.queries.connected_account_query import ConnectedAccountQuery
from app.queries.user_query import UserQuery


async def test_remove_connection(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    user = await UserQuery.find_by_display_name('user1')  # type: ignore
    assert user is not None
    user_id = user['id']

    async with db(True) as conn:
        await conn.execute(
            """
            DELETE FROM connected_account
            WHERE user_id = %s AND provider = 'github'
            """,
            (user_id,),
        )
        await conn.execute(
            """
            INSERT INTO connected_account (user_id, provider, uid)
            VALUES (%s, 'github', 'dev-test')
            """,
            (user_id,),
        )

    r = await client.post(
        '/rpc/settings_connections.Service/Remove',
        headers={'Content-Type': 'application/proto'},
        content=RemoveRequest(provider='github').SerializeToString(),
    )
    assert r.is_success, r.text

    accounts = await ConnectedAccountQuery.find_by_user(user_id)
    assert 'github' not in {a['provider'] for a in accounts}
