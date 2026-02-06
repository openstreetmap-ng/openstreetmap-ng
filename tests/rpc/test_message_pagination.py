from httpx import AsyncClient

from app.models.proto.message_pb2 import (
    GetMessagesPageRequest,
    GetMessagesPageResponse,
    SendMessageRequest,
    SendMessageResponse,
)


async def test_messages_inbox_page_standard_pagination(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    subject = test_messages_inbox_page_standard_pagination.__qualname__
    r = await client.post(
        '/rpc/MessageService/SendMessage',
        headers={'Content-Type': 'application/proto'},
        content=SendMessageRequest(
            subject=subject,
            body='Hello from a test message.',
            recipient=['user2'],
        ).SerializeToString(),
    )
    assert r.is_success, r.text

    # Sanity check: ensure redirect looks like /messages/outbox?show=...
    assert SendMessageResponse.FromString(r.content).redirect_url.startswith(
        '/messages/outbox?show='
    )

    client.headers['Authorization'] = 'User user2'

    r = await client.post(
        '/rpc/MessageService/GetMessagesPage',
        headers={'Content-Type': 'application/proto'},
        content=GetMessagesPageRequest(inbox=True).SerializeToString(),
    )
    assert r.is_success, r.text
    page = GetMessagesPageResponse.FromString(r.content)
    assert page.state.current_page == 1
    assert any(m.subject == subject for m in page.messages)


async def test_messages_outbox_page_standard_pagination(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    subject = test_messages_outbox_page_standard_pagination.__qualname__
    r = await client.post(
        '/rpc/MessageService/SendMessage',
        headers={'Content-Type': 'application/proto'},
        content=SendMessageRequest(
            subject=subject,
            body='Hello from a test message.',
            recipient=['user2'],
        ).SerializeToString(),
    )
    assert r.is_success, r.text

    r = await client.post(
        '/rpc/MessageService/GetMessagesPage',
        headers={'Content-Type': 'application/proto'},
        content=GetMessagesPageRequest(inbox=False).SerializeToString(),
    )
    assert r.is_success, r.text
    page = GetMessagesPageResponse.FromString(r.content)
    assert page.state.current_page == 1
    assert any(m.subject == subject for m in page.messages)
