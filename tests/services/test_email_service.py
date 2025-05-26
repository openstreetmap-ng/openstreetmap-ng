import pytest
from httpx import AsyncClient
from starlette import status

from app.lib.auth_context import auth_context
from app.models.types import DisplayName, LocaleCode
from app.queries.user_query import UserQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.diary_comment_service import DiaryCommentService
from app.services.diary_service import DiaryService
from speedup.buffered_rand import buffered_rand_urlsafe
from tests.utils.mailpit_helper import MailpitHelper


@pytest.mark.extended
@pytest.mark.flaky(reruns=5, only_rerun=['TimeoutError'])
async def test_diary_comment_notification_and_unsubscribe(client: AsyncClient):
    user1 = await UserQuery.find_one_by_display_name(DisplayName('user1'))
    user2 = await UserQuery.find_one_by_display_name(DisplayName('user2'))

    # Create a diary entry as user1
    with auth_context(user1, ()):
        diary_id = await DiaryService.create(
            title='Test Diary',
            body=test_diary_comment_notification_and_unsubscribe.__qualname__,
            language=LocaleCode('en'),
            point=None,
        )

        # Verify user1 is subscribed to the diary
        assert await UserSubscriptionQuery.is_subscribed('diary', diary_id)

    # Add a comment as user2
    with auth_context(user2, ()):
        comment_body = buffered_rand_urlsafe(16)
        await DiaryCommentService.comment(
            diary_id=diary_id,
            body=comment_body,
        )

    # Find the notification email
    message = await MailpitHelper.search_message(comment_body, recipient=user1)

    # Extract unsubscribe token
    headers = await MailpitHelper.get_headers(message['ID'])
    token = MailpitHelper.extract_list_unsubscribe_token(headers)
    assert token

    # Use token to unsubscribe
    r = await client.post(
        f'/diary/{diary_id}/unsubscribe',
        params={'token': token},
    )
    assert r.status_code == status.HTTP_204_NO_CONTENT

    # Verify user1 is no longer subscribed
    with auth_context(user1, ()):
        assert not await UserSubscriptionQuery.is_subscribed('diary', diary_id)


async def test_diary_unsubscribe_invalid_token(client: AsyncClient):
    user1 = await UserQuery.find_one_by_display_name(DisplayName('user1'))

    with auth_context(user1, ()):
        diary_id = await DiaryService.create(
            title='Test Diary',
            body=test_diary_unsubscribe_invalid_token.__qualname__,
            language=LocaleCode('en'),
            point=None,
        )

    # Try to unsubscribe with an invalid token
    r = await client.post(
        f'/diary/{diary_id}/unsubscribe',
        params={'token': 'invalid_token'},
    )
    assert r.is_client_error

    # Verify user1 is still subscribed
    with auth_context(user1, ()):
        assert await UserSubscriptionQuery.is_subscribed('diary', diary_id)
