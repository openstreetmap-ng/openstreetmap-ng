from base64 import urlsafe_b64decode
from typing import TypeVar

from google.protobuf.message import Message

_M = TypeVar('_M', bound=Message)


def decode_page_state(html: str, message_cls: type[_M]):
    """Decode the proto-page bootstrap state from an SSR-rendered page.

    Locates the `data-page-root` element's `data-state` attribute,
    base64-decodes the value, and parses it as the given proto message class.
    """
    marker = 'data-state="'
    start = html.index(marker, html.index('data-page-root')) + len(marker)
    end = html.index('"', start)
    encoded = html[start:end]
    padded = encoded + '=' * (-len(encoded) % 4)
    return message_cls.FromString(urlsafe_b64decode(padded))
