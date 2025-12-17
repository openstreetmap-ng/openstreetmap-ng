from urllib.parse import parse_qs, urlsplit

from httpx import AsyncClient


async def test_messages_inbox_page_standard_pagination(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    subject = test_messages_inbox_page_standard_pagination.__qualname__
    r = await client.post(
        '/api/web/messages',
        data={
            'subject': subject,
            'body': 'Hello from a test message.',
            'recipient': 'user2',
        },
    )
    assert r.is_success, r.text

    # Sanity check: ensure redirect looks like /messages/outbox?show=...
    parsed_url = urlsplit(r.json()['redirect_url'])
    query_params = parse_qs(parsed_url.query, strict_parsing=True)
    assert 'show' in query_params

    client.headers['Authorization'] = 'User user2'

    r = await client.post(
        '/api/web/messages/inbox',
        headers={'Content-Type': 'application/x-protobuf'},
        content=b'',
    )
    assert r.is_success, r.text
    assert 'X-StandardPagination' in r.headers
    assert subject in r.text


async def test_messages_outbox_page_standard_pagination(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    subject = test_messages_outbox_page_standard_pagination.__qualname__
    r = await client.post(
        '/api/web/messages',
        data={
            'subject': subject,
            'body': 'Hello from a test message.',
            'recipient': 'user2',
        },
    )
    assert r.is_success, r.text

    r = await client.post(
        '/api/web/messages/outbox',
        headers={'Content-Type': 'application/x-protobuf'},
        content=b'',
    )
    assert r.is_success, r.text
    assert 'X-StandardPagination' in r.headers
    assert subject in r.text
