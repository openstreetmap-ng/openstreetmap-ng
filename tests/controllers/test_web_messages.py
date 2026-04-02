from urllib.parse import parse_qs, urlsplit

import pytest
from httpx import AsyncClient
from pydantic import PositiveInt
from starlette import status

from app.exceptions import Exceptions
from app.exceptions.api_error import APIError
from app.lib.auth_context import auth_context
from app.lib.exceptions_context import exceptions_context
from app.models.proto.shared_pb2 import MessageRead
from app.models.types import DisplayName, MessageId
from app.queries.message_query import MessageQuery
from app.queries.user_query import UserQuery
from tests.utils.assert_model import assert_model


async def _send_message(
    client: AsyncClient, subject: str, body: str, recipient: str
) -> MessageId:
    """Helper to send a message and return its ID."""
    r = await client.post(
        '/api/web/messages',
        data={'subject': subject, 'body': body, 'recipient': recipient},
    )
    assert r.is_success, r.text
    parsed_url = urlsplit(r.json()['redirect_url'])
    query_params = parse_qs(parsed_url.query, strict_parsing=True)
    return MessageId(int(query_params['show'][0]))


async def test_message_crud(client: AsyncClient):
    user1 = await UserQuery.find_by_display_name(DisplayName('user1'))

    # Authenticate as user1 (sender)
    client.headers['Authorization'] = 'User user1'

    # CREATE: Send message from user1 to user2
    r = await client.post(
        '/api/web/messages',
        data={
            'subject': 'Test Subject',
            'body': 'Test Body',
            'recipient': 'user2',
        },
    )
    assert r.is_success, r.text

    # Parse message ID from redirect URL: /messages/outbox?show=123
    parsed_url = urlsplit(r.json()['redirect_url'])
    query_params = parse_qs(parsed_url.query, strict_parsing=True)
    message_id = MessageId(int(query_params['show'][0]))

    # Test sender can read their own sent message
    r = await client.get(f'/api/web/messages/{message_id}')
    assert r.is_success, r.text

    msg = MessageRead.FromString(r.content)
    assert msg.sender.display_name == 'user1'
    assert msg.sender.avatar_url
    assert len(msg.recipients) == 1
    assert msg.recipients[0].display_name == 'user2'
    assert msg.recipients[0].avatar_url
    assert not msg.is_recipient
    assert msg.time
    assert msg.subject == 'Test Subject'
    assert msg.body_rich == '<p>Test Body</p>\n'

    with auth_context(user1):
        message = await MessageQuery.get_by_id(message_id)
        assert not message['recipients'][0]['read']  # type: ignore

    # Authenticate as user2 (recipient)
    client.headers['Authorization'] = 'User user2'

    # READ: Get message as recipient
    r = await client.get(f'/api/web/messages/{message_id}')
    assert r.is_success, r.text

    msg = MessageRead.FromString(r.content)
    assert msg.sender.display_name == 'user1'
    assert msg.sender.avatar_url
    assert len(msg.recipients) == 1
    assert msg.recipients[0].display_name == 'user2'
    assert msg.recipients[0].avatar_url
    assert msg.is_recipient
    assert msg.time
    assert msg.subject == 'Test Subject'
    assert msg.body_rich == '<p>Test Body</p>\n'

    with auth_context(user1):
        message = await MessageQuery.get_by_id(message_id)
        assert message['recipients'][0]['read']  # type: ignore

        # UPDATE: Mark message as unread
        r = await client.post(f'/api/web/messages/{message_id}/unread')
        assert r.status_code == status.HTTP_204_NO_CONTENT

        message = await MessageQuery.get_by_id(message_id)
        assert not message['recipients'][0]['read']  # type: ignore

    # DELETE: Delete message
    r = await client.post(f'/api/web/messages/{message_id}/delete')
    assert r.status_code == status.HTTP_204_NO_CONTENT

    # Test accessing deleted message
    r = await client.get(f'/api/web/messages/{message_id}')
    assert r.status_code == status.HTTP_404_NOT_FOUND

    # Authenticate as user1 (sender)
    client.headers['Authorization'] = 'User user1'

    with exceptions_context(Exceptions()), auth_context(user1):
        message = await MessageQuery.get_by_id(message_id)
        assert_model(
            message,
            {
                'from_user_hidden': False,
                'recipients': [
                    {
                        'hidden': True,
                        'user_id': PositiveInt,
                    }
                ],
            },
        )

        # DELETE: Delete message
        r = await client.post(f'/api/web/messages/{message_id}/delete')
        assert r.status_code == status.HTTP_204_NO_CONTENT

        with pytest.raises(APIError, match='Message not found'):
            await MessageQuery.get_by_id(message_id)


async def test_bulk_mark_read(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'
    mid1 = await _send_message(client, 'Bulk Read 1', 'Body 1', 'user2')
    mid2 = await _send_message(client, 'Bulk Read 2', 'Body 2', 'user2')

    # Switch to recipient
    client.headers['Authorization'] = 'User user2'

    # Bulk mark as read
    r = await client.post(
        '/api/web/messages/bulk/read',
        data={'message_id': [str(mid1), str(mid2)]},
    )
    assert r.status_code == status.HTTP_204_NO_CONTENT

    # Verify both are read
    user2 = await UserQuery.find_by_display_name(DisplayName('user2'))
    with auth_context(user2):
        m1 = await MessageQuery.get_by_id(mid1)
        m2 = await MessageQuery.get_by_id(mid2)
        assert m1['recipients'][0]['read']  # type: ignore
        assert m2['recipients'][0]['read']  # type: ignore


async def test_bulk_mark_unread(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'
    mid1 = await _send_message(client, 'Bulk Unread 1', 'Body 1', 'user2')

    # Switch to recipient and read the message first
    client.headers['Authorization'] = 'User user2'
    r = await client.get(f'/api/web/messages/{mid1}')
    assert r.is_success

    # Bulk mark as unread
    r = await client.post(
        '/api/web/messages/bulk/unread',
        data={'message_id': [str(mid1)]},
    )
    assert r.status_code == status.HTTP_204_NO_CONTENT

    # Verify it is unread
    user2 = await UserQuery.find_by_display_name(DisplayName('user2'))
    with auth_context(user2):
        m = await MessageQuery.get_by_id(mid1)
        assert not m['recipients'][0]['read']  # type: ignore


async def test_bulk_delete(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'
    mid1 = await _send_message(client, 'Bulk Del 1', 'Body 1', 'user2')
    mid2 = await _send_message(client, 'Bulk Del 2', 'Body 2', 'user2')

    # Switch to recipient
    client.headers['Authorization'] = 'User user2'

    # Bulk delete
    r = await client.post(
        '/api/web/messages/bulk/delete',
        data={'message_id': [str(mid1), str(mid2)]},
    )
    assert r.is_success
    assert r.json()['deleted'] == 2

    # Verify messages are hidden from recipient
    r = await client.get(f'/api/web/messages/{mid1}')
    assert r.status_code == status.HTTP_404_NOT_FOUND
    r = await client.get(f'/api/web/messages/{mid2}')
    assert r.status_code == status.HTTP_404_NOT_FOUND


async def test_inbox_search(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'
    await _send_message(client, 'Unique Search Subject XYZ', 'Body', 'user2')
    await _send_message(client, 'Another Message', 'Body', 'user2')

    # Switch to recipient
    client.headers['Authorization'] = 'User user2'

    # Search by subject
    r = await client.post(
        '/api/web/messages/inbox?q=Unique+Search+Subject',
        headers={'Content-Type': 'application/x-protobuf'},
        content=b'',
    )
    assert r.is_success
    assert 'X-StandardPagination' in r.headers
