import sys

import pytest
from httpx import AsyncClient

from app.models.types import DisplayName
from app.queries.user_query import UserQuery
from speedup.buffered_rand import buffered_rand_urlsafe
from tests.utils.mailpit_helper import MailpitHelper


@pytest.mark.extended
@pytest.mark.flaky(reruns=5, only_rerun=['TimeoutError'])
@pytest.mark.skipif(sys.platform == 'darwin', reason="So flaky that it's annoying")
async def test_profile_report(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    user1 = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user1 is not None
    user2 = await UserQuery.find_by_display_name(DisplayName('user2'))
    assert user2 is not None

    test_message = f'Test report message {buffered_rand_urlsafe(16)}'

    # Create a profile report on user2 by user1
    r = await client.post(
        '/api/web/reports/',
        data={
            'type': 'user',
            'type_id': user2['id'],
            'action': 'user_profile',
            'body': test_message,
            'category': 'spam',
        },
    )
    assert r.is_success, r.text

    # Find the confirmation email sent
    message = await MailpitHelper.search_message(test_message, recipient=user1)

    # Verify email contents
    assert f'/user-id/{user2["id"]}' in message['HTML']
    assert test_message in message['Text']

    # Now authenticate as moderator to view reports page
    client.headers['Authorization'] = 'User moderator'

    # Get the reports page
    r = await client.get(
        '/api/web/reports/',
        params={
            'page': 1,
            'num_items': 10,
        },
    )
    assert r.is_success, r.text

    # Verify the page contents
    assert '/user/user1' in r.text
    assert '/user/user2' in r.text
    assert test_message in r.text
