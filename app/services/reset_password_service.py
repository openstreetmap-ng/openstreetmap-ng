import asyncio
import time
from collections import deque
from statistics import median

from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.models.db.mail import MailSource
from app.models.types import EmailType
from app.queries.user_query import UserQuery
from app.services.email_service import EmailService
from app.services.user_token_reset_password_service import UserTokenResetPasswordService

_latency_measurements: deque[float] = deque((0.1,), maxlen=10)


class ResetPasswordService:
    @staticmethod
    async def send_reset_link(email: EmailType) -> None:
        """
        Send a password reset link to the given email address (if registered).
        """
        user = await UserQuery.find_one_by_email(email)
        if user is None:
            # simulate latency when user is not registered
            await asyncio.sleep(median(_latency_measurements))
            return

        ts = time.perf_counter()
        token = await UserTokenResetPasswordService.create(user)
        await EmailService.schedule(
            source=MailSource.system,
            from_user=None,
            to_user=user,
            subject='TODO',  # TODO:
            template_name='TODO',
            template_data={'token': UserTokenStructUtils.to_str(token)},
        )
        _latency_measurements.append(time.perf_counter() - ts)
