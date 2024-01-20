import logging
from html import escape

import bleach
import cython
from markdown_it import MarkdownIt

from app.models.db.cache_entry import CacheEntry
from app.models.text_format import TextFormat
from app.services.cache_service import CacheService

_md = MarkdownIt(options_update={'typographer': True})
_md.enable(['replacements', 'smartquotes'])


@cython.cfunc
def _cache_context(text_format: TextFormat) -> str:
    return f'RichText_{text_format.value}'


@cython.cfunc
def _is_allowed_attribute(tag: str, attr: str, _: str) -> cython.char:
    return attr in _allowed_attributes[None] or attr in _allowed_attributes.get(tag, ())


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

    # accelerate cache lookup by id if available
    if cache_id:
        return await CacheService.get_one_by_id(cache_id, factory)
    else:
        return await CacheService.get_one_by_key(text, _cache_context(text_format), factory)


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

_allowed_attributes = {
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
