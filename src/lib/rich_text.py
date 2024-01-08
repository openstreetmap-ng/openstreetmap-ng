import logging
from collections.abc import Sequence
from html import escape
from types import MappingProxyType

import anyio
import bleach
from markdown_it import MarkdownIt
from sqlalchemy import update

from src.db import DB
from src.models.db.cache_entry import CacheEntry
from src.models.text_format import TextFormat
from src.services.cache_service import CacheService

_md = MarkdownIt(options_update={'typographer': True})
_md.enable(['replacements', 'smartquotes'])


def _is_allowed_attribute(tag: str, attr: str, _: str) -> bool:
    return attr in _allowed_attributes[None] or attr in _allowed_attributes.get(tag, ())


def _cache_context(text_format: TextFormat) -> str:
    return f'RichText_{text_format.value}'


class RichText:
    @staticmethod
    def _get_value(text: str, text_format: TextFormat) -> str:
        logging.debug('Processing rich text %r', text_format)

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
            skip_tags=[
                'code',
                'kbd',
                'pre',
                'samp',
                'var',
            ],
            parse_email=True,
        )

        return text_

    @staticmethod
    async def get_cache(text: str, cache_id: bytes | None, text_format: TextFormat) -> CacheEntry:
        """
        Get a rich text cache entry by text and format.

        Generate one if not found.

        If `cache_id` is given, it will be used to accelerate cache lookup.
        """

        async def factory() -> str:
            return RichText._get_value(text, text_format)

        # accelerate cache lookup by id if available
        if cache_id:
            return await CacheService.get_one_by_id(cache_id, factory)
        else:
            return await CacheService.get_one_by_key(text, _cache_context(text_format), factory)


class RichTextMixin:
    __rich_text_fields__: Sequence[tuple[str, TextFormat]] = ()

    async def resolve_rich_text(self) -> None:
        """
        Resolve rich text fields.
        """

        async def resolve_task(field_name: str, text_format: TextFormat) -> None:
            rich_field_name = field_name + '_rich'

            # skip if already resolved
            if getattr(self, rich_field_name) is not None:
                return

            rich_hash_field_name = field_name + '_rich_hash'

            text: str = getattr(self, field_name)
            text_rich_hash: bytes | None = getattr(self, rich_hash_field_name)
            cache = await RichText.get_cache(text, text_rich_hash, text_format)

            # assign new hash if changed
            if text_rich_hash != cache.id:
                async with DB() as session:
                    cls = type(self)
                    stmt = (
                        update(cls)
                        .where(cls.id == self.id, getattr(cls, rich_hash_field_name) == text_rich_hash)
                        .values({rich_hash_field_name: cache.id})
                    )

                    await session.execute(stmt)
                setattr(self, rich_hash_field_name, cache.id)

            # assign value to instance
            setattr(self, rich_field_name, cache)

        # small optimization, don't create task group if at most one field
        if len(self.__rich_text_fields__) <= 1:
            for field_name, text_format in self.__rich_text_fields__:
                await resolve_task(field_name, text_format)
        else:
            async with anyio.create_task_group() as tg:
                for field_name, text_format in self.__rich_text_fields__:
                    tg.start_soon(resolve_task, field_name, text_format)


_allowed_tags = frozenset(
    {
        'a',
        'abbr',
        'acronym',
        'address',
        'aside',
        'audio',
        'b',
        'bdi',
        'bdo',
        'blockquote',
        'br',
        'caption',
        'center',
        'cite',
        'code',
        'col',
        'colgroup',
        'data',
        'del',
        'details',
        'dd',
        'dfn',
        'div',
        'dl',
        'dt',
        'em',
        'figcaption',
        'figure',
        'h1',
        'h2',
        'h3',
        'h4',
        'h5',
        'h6',
        'hgroup',
        'hr',
        'i',
        'img',
        'ins',
        'kbd',
        'li',
        'mark',
        'ol',
        'p',
        'picture',
        'pre',
        'q',
        'rp',
        'rt',
        'ruby',
        's',
        'samp',
        'section',
        'small',
        'source',
        'span',
        'strike',
        'strong',
        'sub',
        'summary',
        'sup',
        'table',
        'tbody',
        'td',
        'tfoot',
        'th',
        'thead',
        'time',
        'title',
        'tr',
        'track',
        'u',
        'ul',
        'var',
        'video',
        'wbr',
    }
)

_allowed_attributes = MappingProxyType(
    {
        # None extends to all tags
        None: {
            'dir',
            'hidden',
            'id',
            'lang',
            'tabindex',
            'title',
            'translate',
        },
        'a': {'href', 'hreflang', 'referrerpolicy', 'type'},
        'audio': {'controls', 'loop', 'muted', 'src'},
        'blockquote': {'cite'},
        'col': {'span'},
        'colgroup': {'span'},
        'data': {'value'},
        'del': {'cite', 'datetime'},
        'details': {'open'},
        'img': {'alt', 'src'},
        'ins': {'cite', 'datetime'},
        'li': {'value'},
        'ol': {'reversed', 'start', 'type'},
        'q': {'cite'},
        'source': {'sizes', 'src', 'srcset', 'type'},
        'td': {'colspan', 'headers', 'rowspan'},
        'th': {'abbr', 'colspan', 'headers', 'rowspan', 'scope'},
        'time': {'datetime', 'pubdate'},
        'track': {'default', 'kind', 'label', 'src', 'srclang'},
        'video': {'controls', 'loop', 'muted', 'poster', 'src'},
    }
)
