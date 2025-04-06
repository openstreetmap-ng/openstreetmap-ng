from asyncio import sleep
from email.header import decode_header, make_header
from time import perf_counter
from typing import TypedDict
from urllib.parse import parse_qs, urlparse

from app.models.db.user import User
from app.utils import HTTP


class MailpitAttachment(TypedDict):
    ContentID: str
    ContentType: str
    FileName: str
    PartID: str
    Size: int


class MailpitAddress(TypedDict):
    Address: str
    Name: str


class MailpitMessageSummary(TypedDict):
    Attachments: list[MailpitAttachment]
    Bcc: list[MailpitAddress]
    Cc: list[MailpitAddress]
    Date: str
    From: MailpitAddress
    HTML: str
    ID: str
    Inline: list[MailpitAttachment]
    MessageID: str
    ReplyTo: list[MailpitAddress]
    ReturnPath: str
    Size: int
    Subject: str
    Tags: list[str]
    Text: str
    To: list[MailpitAddress]


class MailpitMessage(TypedDict):
    Attachments: int
    Bcc: list[MailpitAddress]
    Cc: list[MailpitAddress]
    Created: str
    From: MailpitAddress
    ID: str
    MessageID: str
    Read: bool
    ReplyTo: list[MailpitAddress]
    Size: int
    Snippet: str
    Subject: str
    Tags: list[str]
    To: list[MailpitAddress]


_API_URL = 'http://127.0.0.1:49566/api'


class MailpitHelper:
    @staticmethod
    async def search_message(
        search: str,
        /,
        *,
        recipient: User | None = None,
        timeout: float = 3,
    ) -> MailpitMessageSummary:
        """Search for messages in Mailpit."""
        recipient_email = recipient['email'] if recipient is not None else None
        last_id = ''
        tt = perf_counter() + timeout

        while perf_counter() < tt:
            r = await HTTP.get(f'{_API_URL}/v1/messages')
            r.raise_for_status()

            messages: list[MailpitMessage] = r.json()['messages']
            if not messages:
                await sleep(0.02)
                continue

            for message in messages:
                if message['ID'] == last_id:
                    break

                if recipient_email is not None and all(to['Address'] != recipient_email for to in message['To']):
                    continue

                summary = await MailpitHelper.get_message(message['ID'])
                if search not in summary['Text']:
                    continue

                return summary

            last_id = messages[0]['ID']
            await sleep(0.02)

        raise TimeoutError('No messages found')

    @staticmethod
    async def get_message(message_id: str) -> MailpitMessageSummary:
        """Get a specific message from Mailpit."""
        r = await HTTP.get(f'{_API_URL}/v1/message/{message_id}')
        r.raise_for_status()
        return r.json()

    @staticmethod
    async def get_headers(message_id: str) -> dict[str, list[str]]:
        r = await HTTP.get(f'{_API_URL}/v1/message/{message_id}/headers')
        r.raise_for_status()
        return r.json()

    @staticmethod
    def extract_list_unsubscribe_token(headers: dict[str, list[str]]) -> str | None:
        """Extract the unsubscribe token from a message."""
        for key, values in headers.items():
            if key.lower() != 'list-unsubscribe':
                continue

            for value in values:
                # Decode the MIME encoded-word format
                value = str(make_header(decode_header(value)))

                # Extract the URL from angle brackets
                if value[:1] == '<' and value[-1:] == '>':
                    value = value[1:-1]

                if token := parse_qs(urlparse(value).query).get('token'):
                    return token[0]

            return None

        return None
