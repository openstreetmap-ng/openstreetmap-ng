from enum import Enum


class TextFormat(str, Enum):
    html = 'html'
    markdown = 'markdown'
    plain = 'plain'
