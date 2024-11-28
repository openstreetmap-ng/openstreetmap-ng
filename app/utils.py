import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from httpx import AsyncClient, Timeout

from app.config import USER_AGENT

HTTP = AsyncClient(
    headers={'User-Agent': USER_AGENT},
    timeout=Timeout(15, connect=10),
    follow_redirects=True,
)


# TODO: reporting of deleted accounts (prometheus)
# NOTE: breaking change


def unicode_normalize(text: str) -> str:
    """
    Normalize a string to NFC form.
    """
    return unicodedata.normalize('NFC', text)


def extend_query_params(uri: str, params: dict[str, str], *, fragment: bool = False) -> str:
    """
    Extend the query parameters of a URI.

    >>> extend_query_params('http://example.com', {'foo': 'bar'})
    'http://example.com?foo=bar'
    >>> extend_query_params('http://example.com', {'foo': 'bar'}, fragment=True)
    'http://example.com#foo=bar'
    """
    if not params:
        return uri
    uri_ = urlsplit(uri)
    query = parse_qsl(uri_.fragment if fragment else uri_.query, keep_blank_values=True)
    query.extend(params.items())
    query_str = urlencode(query)
    uri_ = uri_._replace(fragment=query_str) if fragment else uri_._replace(query=query_str)
    return urlunsplit(uri_)


def splitlines_trim(s: str) -> tuple[str, ...]:
    """
    Split a string by lines, trim whitespace from each line, and ignore empty lines.

    >>> splitlines_trim('foo\\n\\nbar\\n')
    ['foo', 'bar']
    """
    return tuple(line_ for line in s.splitlines() if (line_ := line.strip()))


def secure_referer(referer: str | None) -> str:
    """
    Return a secure referer, preventing external redirects.
    """
    return '/' if (not referer or not referer.startswith('/')) else referer
