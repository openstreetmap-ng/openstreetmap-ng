from config import SMTP_MESSAGES_FROM_HOST
from models.mail_from_type import MailFromType
from services.user_token_email_reply_service import UserTokenEmailReplyService


class EmailReplyService:
    @staticmethod
    async def create_address(from_user_id: int, source_type: MailFromType, to_user_id: int) -> str:
        """
        Create a new user email reply address.
        """

        # TODO: if the key is leaked, there is no way to revoke it (possible targeted spam)

        token = await UserTokenEmailReplyService.create(from_user_id, source_type, to_user_id)
        reply_address = f'{token}@{SMTP_MESSAGES_FROM_HOST}'
        return reply_address
