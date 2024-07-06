from app.lib.auth_context import auth_user
from app.models.mail_source import MailSource
from app.services.email_service import EmailService
from app.services.user_token_email_change_service import UserTokenEmailChangeService


class EmailChangeService:
    @staticmethod
    async def send_confirm_email(to_email: str) -> None:
        """
        Send a confirmation email for the email change.
        """
        token = await UserTokenEmailChangeService.create(to_email)
        await EmailService.schedule(
            source=MailSource.system,
            from_user=None,
            to_user=auth_user(required=True),
            subject='TODO',  # TODO:
            template_name='TODO',
            template_data={'token': str(token)},
        )
