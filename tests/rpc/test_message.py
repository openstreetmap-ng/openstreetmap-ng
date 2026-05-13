from datetime import timedelta

import pytest
from httpx import AsyncClient
from pydantic import PositiveInt
from starlette import status

from app.db import db
from app.exceptions import Exceptions
from app.exceptions.api_error import APIError
from app.lib.auth_context import auth_context
from app.lib.date_utils import utcnow
from app.lib.exceptions_context import exceptions_context
from app.models.proto.message_pb2 import (
    DeleteRequest,
    GetPageRequest,
    GetPageResponse,
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


async def test_message_page_search(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    r = await client.post(
        '/rpc/message.Service/Send',
        headers={'Content-Type': 'application/proto'},
        content=SendRequest(
            subject='Bridge survey follow-up',
            body='Please review the bridge notes.',
            recipient=['user2'],
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    bridge_id = MessageId(int(SendResponse.FromString(r.content).id))

    client.headers['Authorization'] = 'User user2'

    r = await client.post(
        '/rpc/message.Service/Send',
        headers={'Content-Type': 'application/proto'},
        content=SendRequest(
            subject='Park cleanup',
            body='Thanks for helping with the park.',
            recipient=['user1'],
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    park_id = MessageId(int(SendResponse.FromString(r.content).id))

    now = utcnow().replace(microsecond=0)
    old_created_at = now - timedelta(days=10)
    recent_created_at = now - timedelta(days=1)
    cutoff = int((now - timedelta(days=5)).timestamp())
    async with db(True) as conn:
        await conn.execute(
            'UPDATE message SET created_at = %s WHERE id = %s',
            (old_created_at, bridge_id),
        )
        await conn.execute(
            'UPDATE message SET created_at = %s WHERE id = %s',
            (recent_created_at, park_id),
        )

    client.headers['Authorization'] = 'User user1'

    r = await client.post(
        '/rpc/message.Service/GetPage',
        headers={'Content-Type': 'application/proto'},
        content=GetPageRequest(
            inbox=False,
            search='bridge',
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    outbox = GetPageResponse.FromString(r.content)
    outbox_subjects = {m.subject for m in outbox.messages}
    assert 'Bridge survey follow-up' in outbox_subjects
    assert 'Park cleanup' not in outbox_subjects

    r = await client.post(
        '/rpc/message.Service/GetPage',
        headers={'Content-Type': 'application/proto'},
        content=GetPageRequest(
            inbox=False,
            search='user2',
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    outbox = GetPageResponse.FromString(r.content)
    outbox_subjects = {m.subject for m in outbox.messages}
    assert 'Bridge survey follow-up' in outbox_subjects
    assert 'Park cleanup' not in outbox_subjects

    r = await client.post(
        '/rpc/message.Service/GetPage',
        headers={'Content-Type': 'application/proto'},
        content=GetPageRequest(
            inbox=True,
            search='park',
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    inbox = GetPageResponse.FromString(r.content)
    inbox_subjects = {m.subject for m in inbox.messages}
    assert 'Park cleanup' in inbox_subjects
    assert 'Bridge survey follow-up' not in inbox_subjects

    r = await client.post(
        '/rpc/message.Service/GetPage',
        headers={'Content-Type': 'application/proto'},
        content=GetPageRequest(
            inbox=False,
            search='bridge',
            created_before=cutoff,
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    outbox = GetPageResponse.FromString(r.content)
    outbox_subjects = {m.subject for m in outbox.messages}
    assert 'Bridge survey follow-up' in outbox_subjects

    r = await client.post(
        '/rpc/message.Service/GetPage',
        headers={'Content-Type': 'application/proto'},
        content=GetPageRequest(
            inbox=False,
            search='bridge',
            created_after=cutoff,
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    outbox = GetPageResponse.FromString(r.content)
    outbox_subjects = {m.subject for m in outbox.messages}
    assert 'Bridge survey follow-up' not in outbox_subjects

    r = await client.post(
        '/rpc/message.Service/GetPage',
        headers={'Content-Type': 'application/proto'},
        content=GetPageRequest(
            inbox=True,
            search='park',
            created_after=cutoff,
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    inbox = GetPageResponse.FromString(r.content)
    inbox_subjects = {m.subject for m in inbox.messages}
    assert 'Park cleanup' in inbox_subjects

    r = await client.post(
        '/rpc/message.Service/GetPage',
        headers={'Content-Type': 'application/proto'},
        content=GetPageRequest(
            inbox=True,
            search='park',
            created_before=cutoff,
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    inbox = GetPageResponse.FromString(r.content)
    inbox_subjects = {m.subject for m in inbox.messages}
    assert 'Park cleanup' not in inbox_subjects

    r = await client.post(
        '/rpc/message.Service/GetPage',
        headers={'Content-Type': 'application/proto'},
        content=GetPageRequest(
            inbox=True,
            search='user2',
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    inbox = GetPageResponse.FromString(r.content)
    inbox_subjects = {m.subject for m in inbox.messages}
    assert 'Park cleanup' in inbox_subjects
    assert 'Bridge survey follow-up' not in inbox_subjects
