import logging
import pathlib
import tomllib
from collections.abc import Sequence
from html import escape

import bleach
import cython
from anyio import create_task_group
from markdown_it import MarkdownIt
from sqlalchemy import update

from app.config import CONFIG_DIR
from app.db import db_commit
from app.limits import RICH_TEXT_CACHE_EXPIRE
from app.models.cache_entry import CacheEntry
from app.models.text_format import TextFormat
from app.services.cache_service import CacheService


@cython.cfunc
def _get_allowed_tags_and_attributes() -> tuple[frozenset[str], dict[str, frozenset[str]]]:
    data = tomllib.loads(pathlib.Path(CONFIG_DIR / 'rich_text.toml').read_text())
    allowed_tags = frozenset(data['allowed_tags'])
    allowed_attributes = {k: frozenset(v) for k, v in data['allowed_attributes'].items()}
    return allowed_tags, allowed_attributes


_allowed_tags, _allowed_attributes = _get_allowed_tags_and_attributes()
_global_allowed_attributes = _allowed_attributes['*']

_linkify_skip_tags = (
    'code',
    'kbd',
    'pre',
    'samp',
    'var',
)

_md = MarkdownIt(options_update={'typographer': True})
_md.enable(('replacements', 'smartquotes'))


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


def process_rich_text(text: str, text_format: TextFormat) -> str:
    """
    Get a rich text string by text and format.

    This function runs synchronously and does not use cache.
    """
    if text_format == TextFormat.markdown:
        text_ = _md.render(text)
        text_ = bleach.clean(
            text_,
            tags=_allowed_tags,
            attributes=_is_allowed_attribute,
            strip=True,
        )
    elif text_format == TextFormat.plain:
        text_ = escape(text)
    else:
        raise NotImplementedError(f'Unsupported rich text format {text_format!r}')

    text_ = bleach.linkify(
        text_,
        skip_tags=_linkify_skip_tags,
        parse_email=True,
    )
    return text_


async def rich_text(text: str, cache_id: bytes | None, text_format: TextFormat) -> CacheEntry:
    """
    Get a rich text cache entry by text and format.

    Generate one if not found.

    If `cache_id` is given, it will be used to accelerate cache lookup.
    """
    cache_context = f'RichText:{text_format.value}'

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
    __rich_text_fields__: Sequence[tuple[str, TextFormat]] = ()

    async def resolve_rich_text(self) -> None:
        """
        Resolve rich text fields.
        """
        fields = self.__rich_text_fields__
        num_fields: cython.int = len(fields)
        if num_fields == 0:
            logging.warning('%s has not defined rich text fields', type(self).__qualname__)
            return

        logging.debug('Resolving %d rich text fields', num_fields)

        # small optimization, skip task group if only one field
        if num_fields == 1:
            field_name, text_format = fields[0]
            await self._resolve_rich_text_task(field_name, text_format)
            return

        async with create_task_group() as tg:
            for field_name, text_format in fields:
                tg.start_soon(self._resolve_rich_text_task, field_name, text_format)

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
                    .where(cls.id == self.id, getattr(cls, rich_hash_field_name) == text_rich_hash)
                    .values({rich_hash_field_name: cache_entry_id})
                )
                await session.execute(stmt)

            logging.debug('Rich text field %r hash changed to %r', field_name, cache_entry_id.hex())
            setattr(self, rich_hash_field_name, cache_entry_id)

        # assign value to instance
        setattr(self, rich_field_name, cache_entry.value.decode())
