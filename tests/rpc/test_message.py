import pytest
from httpx import AsyncClient
from pydantic import PositiveInt
from starlette import status

from app.exceptions import Exceptions
from app.exceptions.api_error import APIError
from app.lib.auth_context import auth_context
from app.lib.exceptions_context import exceptions_context
from app.models.proto.message_pb2 import (
    BatchDeleteRequest,
    BatchDeleteResponse,
    BatchUpdateReadStateRequest,
    BatchUpdateReadStateResponse,
    DeleteRequest,
    GetRequest,
    GetResponse,
    SendRequest,
    SendResponse,
    UpdateReadStateRequest,
    UpdateReadStateResponse,
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
        '/rpc/message.Service/Send',
        headers={'Content-Type': 'application/proto'},
        content=SendRequest(
            subject='Test Subject',
            body='Test Body',
            recipient=['user2'],
        ).SerializeToString(),
    )
    assert r.is_success, r.text

    message_id = MessageId(int(SendResponse.FromString(r.content).id))

    # Test sender can read their own sent message
    r = await client.post(
        '/rpc/message.Service/Get',
        headers={'Content-Type': 'application/proto'},
        content=GetRequest(id=message_id).SerializeToString(),
    )
    assert r.is_success, r.text

    msg = GetResponse.FromString(r.content)
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
        '/rpc/message.Service/Get',
        headers={'Content-Type': 'application/proto'},
        content=GetRequest(id=message_id).SerializeToString(),
    )
    assert r.is_success, r.text

    msg = GetResponse.FromString(r.content)
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
            '/rpc/message.Service/UpdateReadState',
            headers={'Content-Type': 'application/proto'},
            content=UpdateReadStateRequest(
                id=message_id,
                read=False,
            ).SerializeToString(),
        )
        assert r.is_success, r.text
        assert UpdateReadStateResponse.FromString(r.content).updated

        message = await MessageQuery.get_by_id(message_id)
        assert not message['recipients'][0]['read']  # type: ignore

    # DELETE: Delete message
    r = await client.post(
        '/rpc/message.Service/Delete',
        headers={'Content-Type': 'application/proto'},
        content=DeleteRequest(id=message_id).SerializeToString(),
    )
    assert r.is_success, r.text

    # Test accessing deleted message
    r = await client.post(
        '/rpc/message.Service/Get',
        headers={'Content-Type': 'application/proto'},
        content=GetRequest(id=message_id).SerializeToString(),
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
            '/rpc/message.Service/Delete',
            headers={'Content-Type': 'application/proto'},
            content=DeleteRequest(id=message_id).SerializeToString(),
        )
        assert r.is_success, r.text

        with pytest.raises(APIError, match='Message not found'):
            await MessageQuery.get_by_id(message_id)


async def test_message_batch_actions(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    message_ids: list[MessageId] = []
    for subject in ('Batch Subject 1', 'Batch Subject 2'):
        r = await client.post(
            '/rpc/message.Service/Send',
            headers={'Content-Type': 'application/proto'},
            content=SendRequest(
                subject=subject,
                body='Batch Body',
                recipient=['user2'],
            ).SerializeToString(),
        )
        assert r.is_success, r.text
        message_ids.append(MessageId(int(SendResponse.FromString(r.content).id)))

    # Senders cannot update recipient read state.
    r = await client.post(
        '/rpc/message.Service/BatchUpdateReadState',
        headers={'Content-Type': 'application/proto'},
        content=BatchUpdateReadStateRequest(
            id=message_ids,
            read=True,
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    assert BatchUpdateReadStateResponse.FromString(r.content).updated_count == 0

    client.headers['Authorization'] = 'User user2'

    r = await client.post(
        '/rpc/message.Service/BatchUpdateReadState',
        headers={'Content-Type': 'application/proto'},
        content=BatchUpdateReadStateRequest(
            id=message_ids,
            read=True,
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    assert BatchUpdateReadStateResponse.FromString(r.content).updated_count == 2

    user2 = await UserQuery.find_by_display_name(DisplayName('user2'))
    with auth_context(user2):
        for message_id in message_ids:
            message = await MessageQuery.get_by_id(message_id)
            assert message['user_recipient']['read']  # type: ignore

    r = await client.post(
        '/rpc/message.Service/BatchUpdateReadState',
        headers={'Content-Type': 'application/proto'},
        content=BatchUpdateReadStateRequest(
            id=message_ids,
            read=False,
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    assert BatchUpdateReadStateResponse.FromString(r.content).updated_count == 2

    with auth_context(user2):
        for message_id in message_ids:
            message = await MessageQuery.get_by_id(message_id)
            assert not message['user_recipient']['read']  # type: ignore

    r = await client.post(
        '/rpc/message.Service/BatchDelete',
        headers={'Content-Type': 'application/proto'},
        content=BatchDeleteRequest(id=message_ids).SerializeToString(),
    )
    assert r.is_success, r.text
    assert BatchDeleteResponse.FromString(r.content).deleted_count == 2

    with exceptions_context(Exceptions()), auth_context(user2):
        for message_id in message_ids:
            with pytest.raises(APIError, match='Message not found'):
                await MessageQuery.get_by_id(message_id)

    client.headers['Authorization'] = 'User user1'

    r = await client.post(
        '/rpc/message.Service/BatchDelete',
        headers={'Content-Type': 'application/proto'},
        content=BatchDeleteRequest(id=[message_ids[0]]).SerializeToString(),
    )
    assert r.is_success, r.text
    assert BatchDeleteResponse.FromString(r.content).deleted_count == 1

    user1 = await UserQuery.find_by_display_name(DisplayName('user1'))
    with exceptions_context(Exceptions()), auth_context(user1):
        with pytest.raises(APIError, match='Message not found'):
            await MessageQuery.get_by_id(message_ids[0])

        message = await MessageQuery.get_by_id(message_ids[1])
        assert not message['from_user_hidden']
