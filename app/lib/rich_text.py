import logging
import pathlib
from html import escape

import bleach
import cython
import orjson
from markdown_it import MarkdownIt

from app.config import CONFIG_DIR
from app.limits import RICH_TEXT_CACHE_EXPIRE
from app.models.cache_entry import CacheEntry
from app.models.text_format import TextFormat
from app.services.cache_service import CacheService


@cython.cfunc
def _get_allowed_tags_and_attributes() -> tuple[frozenset[str], dict[str, frozenset[str]]]:
    data: dict = orjson.loads(pathlib.Path(CONFIG_DIR / 'rich_text.json').read_bytes())
    allowed_tags = frozenset(data['allowed_tags'])
    allowed_attributes = {k: frozenset(v) for k, v in data['allowed_attributes'].items()}
    return allowed_tags, allowed_attributes


@cython.cfunc
def _cache_context(text_format: TextFormat) -> str:
    return f'RichText:{text_format.value}'


@cython.cfunc
def _is_allowed_attribute(tag: str, attr: str, _: str) -> cython.char:
    return attr in _allowed_attributes[''] or attr in _allowed_attributes.get(tag, ())


_allowed_tags, _allowed_attributes = _get_allowed_tags_and_attributes()

_md = MarkdownIt(options_update={'typographer': True})
_md.enable(['replacements', 'smartquotes'])


@cython.cfunc
def _process(text: str, text_format: TextFormat) -> str:
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
        skip_tags=[  # tags not to linkify in
            'code',
            'kbd',
            'pre',
            'samp',
            'var',
        ],
        parse_email=True,
    )

    return text_


async def rich_text(text: str, cache_id: bytes | None, text_format: TextFormat) -> CacheEntry:
    """
    Get a rich text cache entry by text and format.

    Generate one if not found.

    If `cache_id` is given, it will be used to accelerate cache lookup.
    """

    async def factory() -> str:
        return _process(text, text_format)

    context = _cache_context(text_format)

    # accelerate cache lookup by id if available
    if cache_id is not None:
        return await CacheService.get_one_by_id(cache_id, context, factory, ttl=RICH_TEXT_CACHE_EXPIRE)
    else:
        return await CacheService.get_one_by_key(text, context, factory, ttl=RICH_TEXT_CACHE_EXPIRE)
