import logging
import tomllib
from asyncio import TaskGroup
from collections.abc import Collection, Generator, Iterable, Mapping, Sequence
from html import escape
from pathlib import Path
from typing import Any, Literal, LiteralString, cast
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

from app.config import RICH_TEXT_CACHE_EXPIRE, TRUSTED_HOSTS
from app.db import db
from app.lib.crypto import hash_bytes
from app.models.types import ImageProxyId
from app.services.cache_service import CacheContext, CacheService
from app.services.image_proxy_service import ImageProxyService

TextFormat = Literal['html', 'markdown', 'plain']


async def process_rich_text_markdown(
    text: str,
) -> tuple[str, list[ImageProxyId] | None]:
    """Render markdown text and collect image proxy data."""
    text = text.strip()
    env: dict[str, Any] = {}
    tokens = _MD.parse(text, env)
    proxy_ids = await _prepare_image_proxies(tokens)
    text = _MD.renderer.render(tokens, _MD.options, env)
    return nh3.clean(
        text,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        link_rel=None,
    ), proxy_ids


def process_rich_text_plain(text: str) -> str:
    """Render plain text with linkification."""
    text = text.strip()
    text = escape(text)
    text = _process_plain(text)
    return nh3.clean(
        text,
        tags=_PLAIN_ALLOWED_TAGS,
        attributes=_PLAIN_ALLOWED_ATTRS,
        link_rel=None,
    )


async def rich_text(
    text: str,
    cache_id: bytes | None,
    text_format: TextFormat,
) -> tuple[str, bytes, list[ImageProxyId] | None]:
    """
    Get a rich text cache entry by text and format, generating one if not found.
    If cache_id is provided, it will be used to accelerate cache lookup.
    """
    proxy_result: list[ImageProxyId] | None = None

    async def factory() -> bytes:
        nonlocal proxy_result
        if text_format == 'markdown':
            processed_text, proxy_result = await process_rich_text_markdown(text)
        elif text_format == 'plain':
            processed_text = process_rich_text_plain(text)
        else:
            raise NotImplementedError(f'Unsupported rich text format {text_format!r}')
        return processed_text.encode()

    if cache_id is None:
        cache_id = hash_bytes(text)

    processed_bytes = await CacheService.get(
        cache_id.hex(),  # type: ignore
        CacheContext(f'RichText:{text_format}'),
        factory,
        ttl=RICH_TEXT_CACHE_EXPIRE,
    )

    processed = processed_bytes.decode()
    return processed, cache_id, proxy_result


def _iter_image_tokens(tokens: list[Token]) -> Generator[Token]:
    for token in tokens:
        if token.type == 'image':
            yield token
        children = token.children
        if children:
            yield from _iter_image_tokens(children)


async def _prepare_image_proxies(tokens: list[Token]) -> list[ImageProxyId] | None:
    occurrences: list[tuple[Token, str]] = []
    unique_urls: list[str] = []
    seen: set[str] = set()

    for token in _iter_image_tokens(tokens):
        src = token.attrs.get('src')
        if not isinstance(src, str) or src.startswith('/api/web/img/proxy/'):
            continue

        parts = urlsplit(src)
        if parts.scheme.lower() not in {'http', 'https'}:
            continue

        occurrences.append((token, src))
        if src not in seen:
            seen.add(src)
            unique_urls.append(src)

    if not occurrences:
        return None

    entries = await ImageProxyService.ensure(unique_urls)

    entry_map = {entry['url']: entry for entry in entries}
    ids: list[ImageProxyId] = []

    for token, original in occurrences:
        entry = entry_map.get(original)
        if entry is None:
            continue

        proxy_id = ImageProxyId(entry['id'])
        attrs: dict[str, str | int | float] = token.attrs
        attrs['src'] = f'/api/web/img/proxy/{proxy_id}'
        ids.append(proxy_id)

    return ids


async def resolve_rich_text(
    objs: Iterable[Mapping],
    table: LiteralString,
    field: LiteralString,
    text_format: TextFormat,
    *,
    pk_field: LiteralString = 'id',
) -> None:
    rich_field_name = field + '_rich'
    rich_hash_field_name = field + '_rich_hash'

    # skip if already resolved
    mapping = {
        obj[pk_field]: obj
        for obj in objs
        if rich_field_name not in obj  #
        and obj[field] is not None
    }
    if not mapping:
        return

    async with TaskGroup() as tg:
        tasks = [
            tg.create_task(
                rich_text(obj[field], obj[rich_hash_field_name], text_format)
            )
            for obj in mapping.values()
        ]

    params: list[Any] = []
    proxy_results: dict[Any, list[ImageProxyId]] = {}

    for task, obj in zip(tasks, mapping.values(), strict=True):
        processed, cache_id, proxy_result = task.result()
        obj[rich_field_name] = processed  # type: ignore

        current_hash = obj[rich_hash_field_name]
        if current_hash != cache_id:
            obj[rich_hash_field_name] = cache_id  # type: ignore
            params.extend((obj[pk_field], current_hash, cache_id))
        if proxy_result is not None:
            proxy_results[obj[pk_field]] = proxy_result

    if params:
        async with db(True, autocommit=True) as conn:
            num_rows = len(params) // 3
            await conn.execute(
                SQL("""
                    UPDATE {table} SET {field} = v.new_hash
                    FROM (VALUES {values}) AS v(id, old_hash, new_hash)
                    WHERE {table}.{pk_field} = v.id
                      AND {field} IS NOT DISTINCT FROM v.old_hash
                """).format(
                    table=Identifier(table),
                    field=Identifier(rich_hash_field_name),
                    pk_field=Identifier(pk_field),
                    values=SQL(',').join([SQL('(%s, %s, %s)')] * num_rows),
                ),
                params,
            )

        logging.debug('Rich text %r hash changed for %d objects', field, num_rows)

    if proxy_results:
        await _update_image_proxy_ids(
            mapping.values(), table, field, proxy_results, pk_field=pk_field
        )


async def _update_image_proxy_ids(
    objs: Collection[Mapping],
    table: LiteralString,
    field: LiteralString,
    proxy_results: dict[Any, list[ImageProxyId]],
    *,
    pk_field: LiteralString = 'id',
) -> None:
    """Update image proxy ID arrays in database and prune unused entries."""
    image_proxy_field = field + '_image_proxy_ids'

    # Check if this type supports image proxy persistence
    # Only tables with the *_image_proxy_ids column will persist to database
    first_obj = next(iter(objs))
    if image_proxy_field not in first_obj:
        return

    params = []
    removed_ids: set[ImageProxyId] = set()

    for obj in objs:
        new_ids = proxy_results.get(obj[pk_field])
        if new_ids is None:
            continue

        old_ids: list[ImageProxyId] | None = obj[image_proxy_field]
        if new_ids != old_ids:
            params.extend((obj[pk_field], old_ids, new_ids))
            obj[image_proxy_field] = new_ids  # type: ignore[index]
            if old_ids:
                new_removed_ids = set(old_ids)
                new_removed_ids.difference_update(new_ids)
                removed_ids |= new_removed_ids

    if not params:
        return

    async with db(True, autocommit=True) as conn:
        await conn.execute(
            SQL("""
                UPDATE {table} SET {field} = v.new_ids
                FROM (VALUES {values}) AS v(id, old_ids, new_ids)
                WHERE {table}.id = v.id
                  AND {field} IS NOT DISTINCT FROM v.old_ids
            """).format(
                table=Identifier(table),
                field=Identifier(image_proxy_field),
                values=SQL(',').join(
                    [SQL('(%s, %s::bigint[], %s)')] * (len(params) // 3)
                ),
            ),
            params,
        )

    # TODO: Re-enable image proxy pruning via background service (cache issue)
    # if removed_ids:
    #     await ImageProxyService.prune_unused(list(removed_ids))


def _render_image(
    self: RendererHTML,
    tokens: Sequence[Token],
    idx: int,
    options: OptionsDict,
    env: EnvType,
) -> str:
    token = tokens[idx]
    attrs: dict[str, str | int | float] = token.attrs
    attrs['decoding'] = 'async'
    attrs['loading'] = 'lazy'
    return self.image(tokens, idx, options, env)


def _render_link(
    self: RendererHTML,
    tokens: Sequence[Token],
    idx: int,
    options: OptionsDict,
    env: EnvType,
) -> str:
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
            result.append(
                f'{prefix}<a href="{trusted_href}" rel="{_TRUSTED_LINK_REL}">{match.text}</a>'
                if (trusted_href := _process_trusted_link(href)) is not None
                else f'{prefix}<a href="{href}" rel="{_UNTRUSTED_LINK_REL}">{match.text}</a>'
            )
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
