from asyncio import wait_for
from email.header import decode_header, make_header
from time import monotonic
from typing import TypedDict
from urllib.parse import parse_qs, urlparse

import orjson
import websockets

from app.models.db.user import User
from app.utils import HTTP_INTERNAL


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


_API_URL = 'http://localhost:49566/api'
_API_WS_URL = 'ws://localhost:49566/api/events'


class MailpitHelper:
    @staticmethod
    async def search_message(
        search: str,
        /,
        *,
        recipient: User | None = None,
        timeout: float = 5,
    ):
        """Search for messages in Mailpit."""

        async def check_message(msg: MailpitMessage) -> MailpitMessageSummary | None:
            # Check recipient if specified
            if (
                recipient_email is not None  #
                and all(to['Address'] != recipient_email for to in msg['To'])
            ):
                return None

            # Check if the message contains the search string
            summary = await MailpitHelper.get_message(msg['ID'])
            return summary if search in summary['Text'] else None

        recipient_email = recipient['email'] if recipient is not None else None
        deadline = monotonic() + timeout

        async with websockets.connect(_API_WS_URL) as websocket:
            # Process existing messages
            r = await HTTP_INTERNAL.get(f'{_API_URL}/v1/messages')
            r.raise_for_status()

            # Sorted from newest to oldest
            messages: dict[str, MailpitMessage] = {
                msg['ID']: msg for msg in r.json()['messages']
            }

            for msg in messages.values():
                if (summary := await check_message(msg)) is not None:
                    return summary

            # Process new messages
            while True:
                data = await wait_for(websocket.recv(), deadline - monotonic())

                for line in (
                    data.split(b'\n') if isinstance(data, bytes) else data.split('\n')
                ):
                    if not line:
                        continue

                    event = orjson.loads(line)
                    if event.get('Type') != 'new':  # Listen for new messages only
                        continue

                    msg: MailpitMessage = event['Data']
                    if msg['ID'] in messages:  # Skip if the message was already checked
                        continue

                    if (summary := await check_message(msg)) is not None:
                        return summary

    @staticmethod
    async def get_message(message_id: str) -> MailpitMessageSummary:
        """Get a specific message from Mailpit."""
        r = await HTTP_INTERNAL.get(f'{_API_URL}/v1/message/{message_id}')
        r.raise_for_status()
        return r.json()

    @staticmethod
    async def get_headers(message_id: str) -> dict[str, list[str]]:
        r = await HTTP_INTERNAL.get(f'{_API_URL}/v1/message/{message_id}/headers')
        r.raise_for_status()
        return r.json()

    @staticmethod
    def extract_list_unsubscribe_token(headers: dict[str, list[str]]):
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
