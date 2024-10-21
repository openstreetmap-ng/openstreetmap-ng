import logging
import tomllib
from asyncio import TaskGroup
from collections.abc import Sequence
from enum import Enum
from html import escape
from pathlib import Path

import bleach
import cython
from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML
from markdown_it.token import Token
from markdown_it.utils import EnvType, OptionsDict
from sqlalchemy import update

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
    if text_format == TextFormat.markdown:
        text = _md.render(text)
        text = bleach.clean(
            text,
            tags=_allowed_tags,
            attributes=_is_allowed_attribute,
            strip=True,
        )
    elif text_format == TextFormat.plain:
        text = escape(text)
    else:
        raise NotImplementedError(f'Unsupported rich text format {text_format!r}')

    return bleach.linkify(
        text,
        skip_tags=_linkify_skip_tags,
        parse_email=True,
    )


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
                tg.create_task(self._resolve_rich_text_task(field_name, text_format))

    async def _resolve_rich_text_task(self, field_name: str, text_format: TextFormat) -> None:
        rich_field_name = field_name + '_rich'
        rich_hash_field_name = field_name + '_rich_hash'

        # skip if already resolved
        if getattr(self, rich_field_name) is not None:
            return

        text = getattr(self, field_name)
        text_rich_hash: bytes | None = getattr(self, rich_hash_field_name)
        cache_entry = await rich_text(text, text_rich_hash, text_format)
        cache_entry_id: bytes = cache_entry.id

        # assign new hash if changed
        if text_rich_hash != cache_entry_id:
            async with db_commit() as session:
                cls = type(self)
                stmt = (
                    update(cls)
                    .where(
                        cls.id == self.id,  # pyright: ignore[reportAttributeAccessIssue]
                        getattr(cls, rich_hash_field_name) == text_rich_hash,
                    )
                    .values({rich_hash_field_name: cache_entry_id})
                    .inline()
                )
                await session.execute(stmt)

            logging.debug('Rich text field %r hash was changed', field_name)
            setattr(self, rich_hash_field_name, cache_entry_id)

        # assign value to instance
        setattr(self, rich_field_name, cache_entry.value.decode())


@cython.cfunc
def _get_allowed_tags_and_attributes() -> tuple[frozenset[str], dict[str, frozenset[str]]]:
    data = tomllib.loads(Path('config/rich_text.toml').read_text())
    allowed_tags = frozenset(data['allowed_tags'])
    allowed_attributes = {k: frozenset(v) for k, v in data['allowed_attributes'].items()}
    return allowed_tags, allowed_attributes


@cython.cfunc
def _is_allowed_attribute(tag: str, attr: str, value: str) -> cython.char:
    # check global allowed attributes
    if attr in _global_allowed_attributes:
        return True
    # check tag-specific allowed attributes
    allowed_attributes = _allowed_attributes.get(tag)
    if allowed_attributes is not None:
        return attr in allowed_attributes
    return False


def _render_image(self: RendererHTML, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
    token = tokens[idx]
    token.attrs['decoding'] = 'async'
    token.attrs['fetchpriority'] = 'low'
    token.attrs['loading'] = 'lazy'
    return self.image(tokens, idx, options, env)


_allowed_tags, _allowed_attributes = _get_allowed_tags_and_attributes()
_global_allowed_attributes = _allowed_attributes['*']
_linkify_skip_tags = ('code', 'kbd', 'pre', 'samp', 'var')
_md = MarkdownIt(options_update={'typographer': True})
_md.enable(('replacements', 'smartquotes'))
_md.add_render_rule('image', _render_image)
