import re
from typing import override

from htmlmin import Minifier
from jinja2 import FileSystemLoader

_MINIFIER = Minifier(
    remove_comments=True,
    remove_empty_space=True,
    remove_all_empty_space=True,
    reduce_boolean_attributes=True,
    remove_optional_attribute_quotes=False,
)
_JINJA_ESCAPE_RE = re.compile(r'\{(?:\{.*?\}|%.*?%|#.*?#)\}')
_JINJA_UNESCAPE_RE = re.compile(r'__jinja__(\d+)__')


class OptimizedFileSystemLoader(FileSystemLoader):
    @override
    def get_source(self, environment, template):
        source, path, up_to_date = super().get_source(environment, template + '.html.jinja')

        # Replace Jinja syntax with unique entities
        def repl_escape(match: re.Match[str]) -> str:
            id = len(lookup)
            lookup.append(match[0])
            return f'__jinja__{id:05d}__'

        lookup: list[str] = []
        source = _JINJA_ESCAPE_RE.sub(repl_escape, source)

        # Minify the source
        source = _MINIFIER.minify(source)

        # Restore Jinja syntax
        def repl_unescape(match: re.Match[str]) -> str:
            return lookup[int(match[1])]

        source = _JINJA_UNESCAPE_RE.sub(repl_unescape, source)

        return source, path, up_to_date
