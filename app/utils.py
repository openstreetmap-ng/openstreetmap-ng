import builtins
from os import process_cpu_count
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from httpx import AsyncClient

from app.config import HTTP_TIMEOUT, USER_AGENT

HTTP = AsyncClient(
    headers={'User-Agent': USER_AGENT},
    timeout=HTTP_TIMEOUT.total_seconds(),
    follow_redirects=True,
)


# TODO: reporting of deleted accounts (prometheus)
# NOTE: breaking change


def extend_query_params(
    uri: str, params: dict[str, str], *, fragment: bool = False
) -> str:
    """
    Extend the query parameters of a URI.

    >>> extend_query_params('https://example.com', {'foo': 'bar'})
    'https://example.com?foo=bar'
    >>> extend_query_params('https://example.com', {'foo': 'bar'}, fragment=True)
    'https://example.com#foo=bar'
    """
    if not params:
        return uri
    uri_ = urlsplit(uri)
    query = parse_qsl(uri_.fragment if fragment else uri_.query, keep_blank_values=True)
    query.extend(params.items())
    query_str = urlencode(query)
    uri_ = (
        uri_._replace(fragment=query_str)
        if fragment
        else uri_._replace(query=query_str)
    )
    return urlunsplit(uri_)


def splitlines_trim(s: str) -> list[str]:
    """
    Split a string by lines, trim whitespace from each line, and ignore empty lines.

    >>> splitlines_trim('foo\\n\\nbar\\n')
    ['foo', 'bar']
    """
    return [strip for line in s.splitlines() if (strip := line.strip())]


def calc_num_workers(
    target: int | float = 1.0, *, min: int = 1, max: int = 1024
) -> int:
    """
    Calculate the number of workers to use based on the target value.
    If the target is an integer, it will be used as is.
    If the target is a float, it will multiply the number of available CPUs.
    """
    return builtins.min(
        builtins.max(
            (
                int((process_cpu_count() or 1) * target)
                if isinstance(target, float)
                else target
            ),
            min,
        ),
        max,
    )
