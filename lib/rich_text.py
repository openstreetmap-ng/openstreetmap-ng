import logging
from abc import ABC
from html import escape

import bleach
from markdown_it import MarkdownIt

from models.collections.cache_entry import Cache
from models.text_format import TextFormat

_md = MarkdownIt(options_update={
    'typographer': True,
})

_md.enable([
    'replacements',
    'smartquotes',
])

_allowed_tags = {
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

_allowed_attributes = {
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


def _is_allowed_attribute(tag: str, attr: str, _: str) -> bool:
    return (
        attr in _allowed_attributes[None] or
        attr in _allowed_attributes.get(tag, ()))


class RichText(ABC):
    @staticmethod
    def _get_value(text: str, format: TextFormat) -> str:
        logging.debug('Processing rich text %r', format)

        if format == TextFormat.markdown:
            text_ = _md.render(text)
            text_ = bleach.clean(
                text_,
                tags=_allowed_tags,
                attributes=_is_allowed_attribute,
                strip=True)

        elif format == TextFormat.plain:
            text_ = escape(text)

        else:
            raise NotImplementedError(f'Unsupported rich text format {format!r}')

        text_ = bleach.linkify(
            text_,
            skip_tags=[
                'code',
                'kbd',
                'pre',
                'samp',
                'var',
            ],
            parse_email=True)

        return text_

    @staticmethod
    async def get_cache(text: str, hash: str | None, format: TextFormat) -> Cache:
        if hash and (cache := Cache.find_one_by_id(hash)):
            return cache
        value = RichText._get_value(text, format)
        cache = await Cache.create_from_value(value)
        return cache
