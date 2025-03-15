import logging
import tomllib
from asyncio import TaskGroup
from collections.abc import Iterable, Sequence
from html import escape
from pathlib import Path
from typing import Any, Literal, LiteralString, TypedDict, cast
from urllib.parse import urlsplit, urlunsplit

import cython
import nh3
from linkify_it import LinkifyIt
from linkify_it.main import Match as LinkifyMatch
from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML
from markdown_it.token import Token
from markdown_it.utils import EnvType, OptionsDict
from psycopg.sql import SQL, Identifier

from app.config import TRUSTED_HOSTS
from app.db import db
from app.lib.crypto import hash_bytes
from app.limits import RICH_TEXT_CACHE_EXPIRE
from app.services.cache_service import CacheContext, CacheService

TextFormat = Literal['html', 'markdown', 'plain']


def process_rich_text(text: str, text_format: TextFormat) -> str:
    """
    Get a rich text string by text and format.
    This function runs synchronously and does not use cache.
    """
    text = text.strip()

    if text_format == 'markdown':
        text = _MD.render(text)
        return nh3.clean(
            text,
            tags=_ALLOWED_TAGS,
            attributes=_ALLOWED_ATTRS,
            link_rel=None,
        )

    elif text_format == 'plain':
        text = escape(text)
        text = _process_plain(text)
        return nh3.clean(
            text,
            tags=_PLAIN_ALLOWED_TAGS,
            attributes=_PLAIN_ALLOWED_ATTRS,
            link_rel=None,
        )

    raise NotImplementedError(f'Unsupported rich text format {text_format!r}')


async def rich_text(text: str, cache_id: bytes | None, text_format: TextFormat) -> tuple[str, bytes]:
    """
    Get a rich text cache entry by text and format, generating one if not found.
    If cache_id is provided, it will be used to accelerate cache lookup.
    """

    def factory() -> bytes:
        return process_rich_text(text, text_format).encode()

    if cache_id is None:
        cache_id = hash_bytes(text)

    processed = (
        await CacheService.get(
            cache_id.hex(),  # type: ignore
            CacheContext(f'RichText:{text_format}'),
            factory,
            ttl=RICH_TEXT_CACHE_EXPIRE,
        )
    ).decode()

    return processed, cache_id


class _HasId(TypedDict):
    id: Any


async def resolve_rich_text(
    objs: Iterable[_HasId],
    table: LiteralString,
    field: LiteralString,
    text_format: TextFormat,
) -> None:
    rich_field_name = field + '_rich'
    rich_hash_field_name = field + '_rich_hash'

    # skip if already resolved
    mapping: dict[Any, _HasId] = {obj['id']: obj for obj in objs if rich_field_name not in obj}
    if not mapping:
        return

    async with TaskGroup() as tg:
        tasks = [
            tg.create_task(rich_text(obj[field], obj[rich_hash_field_name], text_format))  # type: ignore
            for obj in mapping.values()
        ]

    # list of (id, current_hash, new_hash)
    to_update: list[tuple[Any, bytes, bytes]] = []

    for task, obj in zip(tasks, mapping.values(), strict=True):
        processed, cache_id = task.result()
        obj[rich_field_name] = processed  # type: ignore

        current_hash: bytes = obj[rich_hash_field_name]  # type: ignore
        if current_hash != cache_id:
            to_update.append((obj['id'], current_hash, cache_id))

    if not to_update:
        return

    async with db(True, autocommit=True) as conn:
        await conn.execute(
            SQL("""
                UPDATE {table} SET {field} = v.new_hash
                FROM (VALUES ({values})) AS v(id, old_hash, new_hash)
                WHERE id = v.id AND {field} = v.old_hash
            """).format(
                table=Identifier(table),
                field=Identifier(rich_hash_field_name),
                values=SQL('), (').join([SQL('%s, %s, %s')] * len(to_update)),
            ),
            [v for vals in to_update for v in vals],
        )

    logging.debug('Rich text %r hash changed for %d objects', field, len(to_update))


def _render_image(self: RendererHTML, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
    token = tokens[idx]
    attrs: dict[str, str | int | float] = token.attrs
    attrs['decoding'] = 'async'
    attrs['loading'] = 'lazy'
    return self.image(tokens, idx, options, env)


def _render_link(self: RendererHTML, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
    token = tokens[idx]
    attrs: dict[str, str | int | float] = token.attrs
    trusted_href = _process_trusted_link(attrs.get('href'))
    if trusted_href is not None:
        attrs['href'] = trusted_href
        attrs['rel'] = _TRUSTED_LINK_REL
    else:
        attrs['rel'] = _UNTRUSTED_LINK_REL
    return self.renderToken(tokens, idx, options, env)


@cython.cfunc
def _process_trusted_link(href: str | float | None):
    if href is None:
        return None

    parts = urlsplit(str(href))
    hostname = parts.hostname
    if hostname is None:
        # relative, absolute, or empty href
        return href

    hostname = hostname.casefold()
    if hostname not in TRUSTED_HOSTS and not hostname.endswith(_TRUSTED_HOSTS_DOT):
        return None

    # href is trusted, upgrade to https
    if parts.scheme == 'http':
        return urlunsplit(parts._replace(scheme='https'))

    return href


@cython.cfunc
def _process_plain(text: str) -> str:
    """
    Process plain text by linkifying URLs,
    converting newlines to <br> tags,
    and wrapping entire content in a <p> tag.
    """
    if not text:
        return '<p></p>'

    matches: list[LinkifyMatch] | None = _LINKIFY.match(text)
    if matches is None:
        # optimize for text without any links
        text = f'<p>{text}</p>'
    else:
        result: list[str] = ['<p>']

        last_pos: int = 0
        for match in matches:
            prefix = text[last_pos : match.index]
            href = match.url
            trusted_href = _process_trusted_link(href)
            if trusted_href is not None:
                result.append(f'{prefix}<a href="{trusted_href}" rel="{_TRUSTED_LINK_REL}">{match.text}</a>')
            else:
                result.append(f'{prefix}<a href="{href}" rel="{_UNTRUSTED_LINK_REL}">{match.text}</a>')
            last_pos = match.last_index

        # add remaining text after last link
        if last_pos < len(text):
            suffix = text[last_pos:]
            result.append(suffix)

        result.append('</p>')
        text = ''.join(result)

    return text.replace('\n', '<br>')


@cython.cfunc
def _load_allowed_tags_and_attributes() -> tuple[set[str], dict[str, set[str]]]:
    data = tomllib.loads(Path('config/rich_text.toml').read_text())
    allowed_tags = set(data['allowed_tags'])
    allowed_attributes = {k: set(v) for k, v in data['allowed_attributes'].items()}
    return allowed_tags, allowed_attributes


_ALLOWED_TAGS, _ALLOWED_ATTRS = _load_allowed_tags_and_attributes()
_PLAIN_ALLOWED_TAGS = {'p', 'br', 'a'}
_PLAIN_ALLOWED_ATTRS = {'a': {'href', 'rel'}}
_MD = MarkdownIt('commonmark', {'linkify': True, 'typographer': True})
_MD.enable(('linkify', 'smartquotes', 'replacements'))
_MD.add_render_rule('image', _render_image)
_MD.add_render_rule('link_open', _render_link)
_LINKIFY = cast(LinkifyIt, _MD.linkify)
_LINKIFY.tlds('onion', keep_old=True)  # support onion links
_LINKIFY.add('ftp:', None)  # disable ftp links
_LINKIFY.add('//', None)  # disable double-slash links
_TRUSTED_HOSTS_DOT = tuple(f'.{host}' for host in TRUSTED_HOSTS)
_TRUSTED_LINK_REL = 'noopener'
_UNTRUSTED_LINK_REL = 'noopener nofollow'
