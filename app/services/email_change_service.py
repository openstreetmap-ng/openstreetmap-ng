from urllib.parse import urlsplit

from app.config import APP_URL
from app.lib.auth_context import auth_user
from app.lib.translation import t
from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.models.db.mail import MailSource
from app.models.types import EmailType
from app.services.email_service import EmailService
from app.services.user_token_email_change_service import UserTokenEmailChangeService


class EmailChangeService:
    @staticmethod
    async def send_confirm_email(new_email: EmailType) -> None:
        """
        Send a confirmation email for the email change.
        """
        app_domain = urlsplit(APP_URL).netloc
        token = await UserTokenEmailChangeService.create(new_email)
        await EmailService.schedule(
            source=MailSource.system,
            from_user=None,
            to_user=auth_user(required=True),
            subject=t('user_mailer.email_confirm.subject'),
            template_name='email/email_change_confirm.jinja2',
            template_data={
                'new_email': new_email,
                'token': UserTokenStructUtils.to_str(token),
                'app_domain': app_domain,
            },
        )
