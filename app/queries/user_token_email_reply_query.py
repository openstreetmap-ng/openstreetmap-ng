import logging
from email.utils import parseaddr

from pydantic import SecretStr

from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.models.db.user_token import UserTokenEmailReply
from app.models.types import Email
from app.queries.user_token_query import UserTokenQuery


class UserTokenEmailReplyQuery:
    @staticmethod
    async def find_by_reply_address(
        reply_address: Email,
    ) -> UserTokenEmailReply | None:
        """Find a user email reply token by reply email address."""
        # Strip the name part: "abc" <foo@bar.com> -> foo@bar.com
        reply_address = Email(parseaddr(reply_address)[1])
        try:
            token_str = SecretStr(reply_address.split('@', 1)[0])
            token_struct = UserTokenStructUtils.from_str(token_str)
        except Exception:
            logging.debug('Invalid reply address format %r', reply_address)
            return None

        return await UserTokenQuery.find_by_token_struct('email_reply', token_struct)
