import logging
import tomllib
from asyncio import TaskGroup
from collections.abc import Iterable, Sequence
from enum import Enum
from html import escape
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit, urlunsplit

import cython
import nh3
from linkify_it import LinkifyIt
from linkify_it.main import Match as LinkifyMatch
from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML
from markdown_it.token import Token
from markdown_it.utils import EnvType, OptionsDict
from sqlalchemy import update

from app.config import TRUSTED_HOSTS
from app.db import db_commit
from app.limits import RICH_TEXT_CACHE_EXPIRE
from app.services.cache_service import CacheContext, CacheEntry, CacheService


class TextFormat(str, Enum):
    html = 'html'
    markdown = 'markdown'
    plain = 'plain'


def process_rich_text(text: str, text_format: TextFormat) -> str:
    """
    Get a rich text string by text and format.

    This function runs synchronously and does not use cache.
    """
    text = text.strip()
    if text_format == TextFormat.markdown:
        text = _md.render(text)
        return nh3.clean(
            text,
            tags=_allowed_tags,
            attributes=_allowed_attributes,
            link_rel=None,
        )
    elif text_format == TextFormat.plain:
        text = escape(text)
        text = _process_plain(text)
        return nh3.clean(
            text,
            tags=_plain_allowed_tags,
            attributes=_plain_allowed_attributes,
            link_rel=None,
        )
    else:
        raise NotImplementedError(f'Unsupported rich text format {text_format!r}')


async def rich_text(text: str, cache_id: bytes | None, text_format: TextFormat) -> CacheEntry:
    """
    Get a rich text cache entry by text and format, generating one if not found.

    If cache_id is provided, it will be used to accelerate cache lookup.
    """
    cache_context = CacheContext(f'RichText:{text_format.value}')

    async def factory() -> bytes:
        return process_rich_text(text, text_format).encode()

    # accelerate cache lookup by id if available
    if cache_id is not None:
        return await CacheService.get(
            cache_id,
            cache_context,
            factory,
            ttl=RICH_TEXT_CACHE_EXPIRE,
        )
    else:
        return await CacheService.get(
            text,
            cache_context,
            factory,
            hash_key=True,
            ttl=RICH_TEXT_CACHE_EXPIRE,
        )


class RichTextMixin:
    __rich_text_fields__: tuple[tuple[str, TextFormat], ...] = ()

    async def resolve_rich_text(self) -> None:
        """
        Resolve rich text fields.
        """
        fields = self.__rich_text_fields__
        num_fields: int = len(fields)
        if num_fields == 0:
            logging.warning('%s has not defined rich text fields', type(self).__qualname__)
            return

        logging.debug('Resolving %d rich text fields', num_fields)
        async with TaskGroup() as tg:
            for field_name, text_format in fields:
                tg.create_task(_resolve_rich_text_task(self, field_name, text_format))


async def _resolve_rich_text_task(self, field_name: str, text_format: TextFormat) -> None:
    rich_field_name = field_name + '_rich'
    rich_hash_field_name = field_name + '_rich_hash'

    # skip if already resolved
    if getattr(self, rich_field_name) is not None:
        return

    text: str = getattr(self, field_name)
    text_rich_hash: bytes | None = getattr(self, rich_hash_field_name)
    cache_entry = await rich_text(text, text_rich_hash, text_format)
    cache_entry_id: bytes = cache_entry.id

    # assign new hash if changed
    if text_rich_hash != cache_entry_id:
        updated_at = getattr(self, 'updated_at', None)
        async with db_commit() as session:
            cls = type(self)
            stmt = (
                update(cls)
                .where(
                    cls.id == self.id,
                    getattr(cls, rich_hash_field_name) == text_rich_hash,
                )
                .values(
                    {
                        rich_hash_field_name: cache_entry_id,
                        # preserve updated_at if it exists
                        **({'updated_at': updated_at} if (updated_at is not None) else {}),
                    }
                )
                .inline()
            )
            await session.execute(stmt)

        logging.debug('Rich text field %r hash was changed', field_name)
        setattr(self, rich_hash_field_name, cache_entry_id)

    # assign value to instance
    setattr(self, rich_field_name, cache_entry.value.decode())


@cython.cfunc
def _get_allowed_tags_and_attributes() -> tuple[set[str], dict[str, set[str]]]:
    data = tomllib.loads(Path('config/rich_text.toml').read_text())
    allowed_tags = set(data['allowed_tags'])
    allowed_attributes = {k: set(v) for k, v in data['allowed_attributes'].items()}
    return allowed_tags, allowed_attributes


def _render_image(self: RendererHTML, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
    token = tokens[idx]
    token.attrs['decoding'] = 'async'
    token.attrs['loading'] = 'lazy'
    return self.image(tokens, idx, options, env)


def _render_link(self: RendererHTML, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
    token = tokens[idx]
    trusted_href = _process_trusted_link(token.attrs.get('href'))
    if trusted_href is not None:
        token.attrs['href'] = trusted_href
        token.attrs['rel'] = _trusted_link_rel
    else:
        token.attrs['rel'] = _untrusted_link_rel
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
    if hostname not in _trusted_hosts and not any(hostname.endswith(host) for host in _trusted_hosts_dot):
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

    matches: Iterable[LinkifyMatch] | None = _linkify.match(text)
    if matches is None:
        # small optimization for text without links (most common)
        text = f'<p>{text}</p>'
    else:
        result: list[str] = ['<p>']
        last_pos: int = 0
        for match in matches:
            prefix = text[last_pos : match.index]
            href = match.url
            trusted_href = _process_trusted_link(href)
            if trusted_href is not None:
                result.append(f'{prefix}<a href="{trusted_href}" rel="{_trusted_link_rel}">{match.text}</a>')
            else:
                result.append(f'{prefix}<a href="{href}" rel="{_untrusted_link_rel}">{match.text}</a>')
            last_pos = match.last_index
        # add remaining text after last link
        if last_pos < len(text):
            suffix = text[last_pos:]
            result.append(suffix)
        result.append('</p>')
        text = ''.join(result)

    return text.replace('\n', '<br>')


_allowed_tags, _allowed_attributes = _get_allowed_tags_and_attributes()
_plain_allowed_tags = {'p', 'br', 'a'}
_plain_allowed_attributes = {'a': {'href', 'rel'}}
_md = MarkdownIt('commonmark', {'linkify': True, 'typographer': True})
_md.enable(('linkify', 'smartquotes', 'replacements'))
_md.add_render_rule('image', _render_image)
_md.add_render_rule('link_open', _render_link)
_linkify = cast(LinkifyIt, _md.linkify)
_linkify.tlds('onion', keep_old=True)  # support onion links
_linkify.add('ftp:', None)  # disable ftp links
_linkify.add('//', None)  # disable double-slash links
_trusted_hosts = TRUSTED_HOSTS
_trusted_hosts_dot = tuple(f'.{host}' for host in TRUSTED_HOSTS)
_trusted_link_rel = 'noopener'
_untrusted_link_rel = 'noopener nofollow'
