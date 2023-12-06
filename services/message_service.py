from db import DB
from lib.auth import auth_user
from models.db.message import Message


class MessageService:
    @staticmethod
    async def send(to_user_id: int, subject: str, body: str) -> None:
        """
        Send a message to a user.
        """

        async with DB() as session:
            session.add(
                Message(
                    from_user_id=auth_user().id,
                    to_user_id=to_user_id,
                    subject=subject,
                    body=body,
                )
            )
