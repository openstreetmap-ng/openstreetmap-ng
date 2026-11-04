import pytest
from httpx import AsyncClient

from app.models.proto.message_pb2 import (
    DeleteRequest,
    GetPageRequest,
    GetPageResponse,
    GetRequest,
    GetResponse,
    SendRequest,
    SendResponse,
)


async def test_messages_inbox_page_standard_pagination(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    subject = test_messages_inbox_page_standard_pagination.__qualname__
    r = await client.post(
        '/rpc/message.Service/Send',
        headers={'Content-Type': 'application/proto'},
        content=SendRequest(
            subject=subject,
            body='Hello from a test message.',
            recipient=['user2'],
        ).SerializeToString(),
    )
    assert r.is_success, r.text

    assert SendResponse.FromString(r.content).id > 0

    client.headers['Authorization'] = 'User user2'

    r = await client.post(
        '/rpc/message.Service/GetPage',
        headers={'Content-Type': 'application/proto'},
        content=GetPageRequest(inbox=True).SerializeToString(),
    )
    assert r.is_success, r.text
    page = GetPageResponse.FromString(r.content)
    assert page.state.current_page == 1
    assert any(m.subject == subject for m in page.messages)


async def test_mailbox_filters_and_ownership(client: AsyncClient):
    subject = 'Mailbox filter literal %_ and mixed CASE'
    client.headers['Authorization'] = 'User user1'
    r = await client.post(
        '/rpc/message.Service/Send',
        headers={'Content-Type': 'application/proto'},
        content=SendRequest(
            subject=subject, body='Filter test', recipient=['user2']
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    message_id = SendResponse.FromString(r.content).id
    r = await client.post(
        '/rpc/message.Service/Get',
        headers={'Content-Type': 'application/proto'},
        content=GetRequest(id=message_id).SerializeToString(),
    )
    assert r.is_success, r.text
    created = GetResponse.FromString(r.content).created_at

    async def ids(user, **filters):
        client.headers['Authorization'] = f'User {user}'
        r = await client.post(
            '/rpc/message.Service/GetPage',
            headers={'Content-Type': 'application/proto'},
            content=GetPageRequest(**filters).SerializeToString(),
        )
        assert r.is_success, r.text
        return {
            message.id for message in GetPageResponse.FromString(r.content).messages
        }

    # Sender and recipient search use the opposite party, not the viewer.
    assert message_id in await ids(
        'user2', inbox=True, search_user='USER1', search_subject='%_'
    )
    assert message_id in await ids(
        'user1', inbox=False, search_user='UsEr2', search_subject='mixed case'
    )
    assert message_id not in await ids(
        'user2', inbox=True, search_user='user2', search_subject=subject
    )
    # A literal percent/underscore is not a SQL wildcard; filters do not grant access.
    assert not await ids('user2', inbox=True, search_subject='%_%_')
    assert message_id not in await ids('user1', inbox=True, search_subject=subject)
    assert message_id not in await ids('user2', inbox=False, search_subject=subject)
    assert message_id in await ids(
        'user2',
        inbox=True,
        search_subject=subject,
        created_after=created,
        created_before=created + 1,
    )
    assert message_id not in await ids(
        'user2', inbox=True, search_subject=subject, created_before=created - 1
    )
    assert message_id not in await ids(
        'user2', inbox=True, search_subject=subject, created_after=created + 1
    )

    client.headers['Authorization'] = 'User user2'
    r = await client.post(
        '/rpc/message.Service/Delete',
        headers={'Content-Type': 'application/proto'},
        content=DeleteRequest(id=message_id).SerializeToString(),
    )
    assert r.is_success, r.text
    assert message_id not in await ids('user2', inbox=True, search_subject=subject)
    # Hiding a recipient copy must not hide the sender's outbox copy.
    assert message_id in await ids('user1', inbox=False, search_subject=subject)


@pytest.mark.parametrize(
    'filters',
    [
        {'created_after': 200, 'created_before': 100},
        {'created_after': 253402300800},
        {'created_before': 253402300800},
        {'search_user': ''},
        {'search_subject': ''},
        {'search_user': 'x' * 256},
        {'search_subject': 'x' * 101},
    ],
)
async def test_mailbox_rejects_invalid_filters(client: AsyncClient, filters):
    client.headers['Authorization'] = 'User user1'
    r = await client.post(
        '/rpc/message.Service/GetPage',
        headers={'Content-Type': 'application/proto'},
        content=GetPageRequest(inbox=True, **filters).SerializeToString(),
    )
    assert r.status_code == 400, r.text


async def test_messages_outbox_page_standard_pagination(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    subject = test_messages_outbox_page_standard_pagination.__qualname__
    r = await client.post(
        '/rpc/message.Service/Send',
        headers={'Content-Type': 'application/proto'},
        content=SendRequest(
            subject=subject,
            body='Hello from a test message.',
            recipient=['user2'],
        ).SerializeToString(),
    )
    assert r.is_success, r.text

    r = await client.post(
        '/rpc/message.Service/GetPage',
        headers={'Content-Type': 'application/proto'},
        content=GetPageRequest(inbox=False).SerializeToString(),
    )
    assert r.is_success, r.text
    page = GetPageResponse.FromString(r.content)
    assert page.state.current_page == 1
    assert any(m.subject == subject for m in page.messages)
