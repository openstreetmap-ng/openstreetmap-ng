from httpx import AsyncClient

from app.models.proto.message_pb2 import (
    GetPageRequest,
    GetPageResponse,
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

    # Sanity check: ensure redirect looks like /messages/outbox?show=...
    assert SendResponse.FromString(r.content).redirect_url.startswith(
        '/messages/outbox?show='
    )

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
