import logging

from app.lib.exceptions_context import raise_for
from app.models.db.user_subscription import UserSubscriptionTarget
from app.models.proto.server_pb2 import StatelessUserTokenStruct
from app.models.types import UserSubscriptionTargetId
from app.services.user_subscription_service import UserSubscriptionService


class UserTokenUnsubscribeService:
    @staticmethod
    async def unsubscribe(
        target: UserSubscriptionTarget,
        target_id: UserSubscriptionTargetId,
        token_struct: StatelessUserTokenStruct,
    ):
        """Unsubscribe user from the given target."""
        if not (
            token_struct.HasField('unsubscribe')
            and token_struct.unsubscribe.target == target
            and token_struct.unsubscribe.target_id == target_id
        ):
            logging.info('Invalid user token context')
            raise_for.bad_user_token_struct()

        await UserSubscriptionService.unsubscribe(
            target=target,
            target_id=target_id,
            user_id=token_struct.user_id,  # type: ignore
        )
