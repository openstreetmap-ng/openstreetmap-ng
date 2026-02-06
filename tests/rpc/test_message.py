from urllib.parse import parse_qs, urlsplit

import pytest
from httpx import AsyncClient
from pydantic import PositiveInt
from starlette import status

from app.exceptions import Exceptions
from app.exceptions.api_error import APIError
from app.lib.auth_context import auth_context
from app.lib.exceptions_context import exceptions_context
from app.models.proto.message_pb2 import (
    DeleteMessageRequest,
    GetMessageRequest,
    GetMessageResponse,
    SendMessageRequest,
    SendMessageResponse,
    SetMessageReadStateRequest,
    SetMessageReadStateResponse,
)
from app.models.types import DisplayName, MessageId
from app.queries.message_query import MessageQuery
from app.queries.user_query import UserQuery
from tests.utils.assert_model import assert_model


async def test_message_crud(client: AsyncClient):
    user1 = await UserQuery.find_by_display_name(DisplayName('user1'))

    # Authenticate as user1 (sender)
    client.headers['Authorization'] = 'User user1'

    # CREATE: Send message from user1 to user2
    r = await client.post(
        '/rpc/MessageService/SendMessage',
        headers={'Content-Type': 'application/proto'},
        content=SendMessageRequest(
            subject='Test Subject',
            body='Test Body',
            recipient=['user2'],
        ).SerializeToString(),
    )
    assert r.is_success, r.text

    # Parse message ID from redirect URL: /messages/outbox?show=123
    create_resp = SendMessageResponse.FromString(r.content)
    parsed_url = urlsplit(create_resp.redirect_url)
    query_params = parse_qs(parsed_url.query, strict_parsing=True)
    message_id = MessageId(int(query_params['show'][0]))

    # Test sender can read their own sent message
    r = await client.post(
        '/rpc/MessageService/GetMessage',
        headers={'Content-Type': 'application/proto'},
        content=GetMessageRequest(id=message_id).SerializeToString(),
    )
    assert r.is_success, r.text

    msg = GetMessageResponse.FromString(r.content)
    assert msg.sender.display_name == 'user1'
    assert msg.sender.avatar_url
    assert len(msg.recipients) == 1
    assert msg.recipients[0].display_name == 'user2'
    assert msg.recipients[0].avatar_url
    assert not msg.is_recipient
    assert msg.created_at
    assert msg.subject == 'Test Subject'
    assert msg.body_rich == '<p>Test Body</p>\n'

    with auth_context(user1):
        message = await MessageQuery.get_by_id(message_id)
        assert not message['recipients'][0]['read']  # type: ignore

    # Authenticate as user2 (recipient)
    client.headers['Authorization'] = 'User user2'

    # READ: Get message as recipient
    r = await client.post(
        '/rpc/MessageService/GetMessage',
        headers={'Content-Type': 'application/proto'},
        content=GetMessageRequest(id=message_id).SerializeToString(),
    )
    assert r.is_success, r.text

    msg = GetMessageResponse.FromString(r.content)
    assert msg.sender.display_name == 'user1'
    assert msg.sender.avatar_url
    assert len(msg.recipients) == 1
    assert msg.recipients[0].display_name == 'user2'
    assert msg.recipients[0].avatar_url
    assert msg.is_recipient
    assert msg.created_at
    assert msg.subject == 'Test Subject'
    assert msg.body_rich == '<p>Test Body</p>\n'

    with auth_context(user1):
        message = await MessageQuery.get_by_id(message_id)
        assert message['recipients'][0]['read']  # type: ignore

        # UPDATE: Mark message as unread
        r = await client.post(
            '/rpc/MessageService/SetMessageReadState',
            headers={'Content-Type': 'application/proto'},
            content=SetMessageReadStateRequest(
                id=message_id,
                read=False,
            ).SerializeToString(),
        )
        assert r.is_success, r.text
        assert SetMessageReadStateResponse.FromString(r.content).updated

        message = await MessageQuery.get_by_id(message_id)
        assert not message['recipients'][0]['read']  # type: ignore

    # DELETE: Delete message
    r = await client.post(
        '/rpc/MessageService/DeleteMessage',
        headers={'Content-Type': 'application/proto'},
        content=DeleteMessageRequest(id=message_id).SerializeToString(),
    )
    assert r.is_success, r.text

    # Test accessing deleted message
    r = await client.post(
        '/rpc/MessageService/GetMessage',
        headers={'Content-Type': 'application/proto'},
        content=GetMessageRequest(id=message_id).SerializeToString(),
    )
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
        r = await client.post(
            '/rpc/MessageService/DeleteMessage',
            headers={'Content-Type': 'application/proto'},
            content=DeleteMessageRequest(id=message_id).SerializeToString(),
        )
        assert r.is_success, r.text

        with pytest.raises(APIError, match='Message not found'):
            await MessageQuery.get_by_id(message_id)
