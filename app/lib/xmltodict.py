import logging
from typing import Any, Literal, Protocol, overload

from sizestr import sizestr

from app.config import XML_PARSE_MAX_SIZE
from app.lib.exceptions_context import raise_for
from app.lib.format_style_context import format_is_json
from optimized.xml_parse import xml_parse
from optimized.xml_unparse import xml_unparse


class XMLToDict:
    @staticmethod
    def parse(
        xml_bytes: bytes, *, size_limit: int | None = XML_PARSE_MAX_SIZE
    ) -> dict[str, dict[str, Any] | list[tuple[str, Any]]]:
        """Parse XML string to dict."""
        if size_limit is not None and len(xml_bytes) > size_limit:
            raise_for.input_too_big(len(xml_bytes))

        logging.debug('Parsing %s XML string', sizestr(len(xml_bytes)))

        try:
            return xml_parse(xml_bytes)
        except ValueError as e:
            raise_for.bad_xml('data', str(e), xml_bytes)

    @staticmethod
    @overload
    def unparse(d: dict[str, Any]) -> str: ...
    @staticmethod
    @overload
    def unparse(d: dict[str, Any], *, binary: Literal[True]) -> bytes: ...
    @staticmethod
    @overload
    def unparse(d: dict[str, Any], *, binary: Literal[False]) -> str: ...
    @staticmethod
    def unparse(d: dict[str, Any], *, binary: bool = False) -> str | bytes:
        """Unparse dict to XML string."""
        result = xml_unparse(d, binary)
        logging.debug('Unparsed %s XML string', sizestr(len(result)))
        return result


class _XAttrCallable(Protocol):
    def __call__(self, name: str, xml: str | None = None) -> str: ...


def _xattr_json(name: str, xml=None) -> str:
    return name


def _xattr_xml(name: str, xml: str | None = None) -> str:
    return '@' + (xml or name)


def get_xattr(*, is_json: bool | None = None) -> _XAttrCallable:
    """
    Return a function to format attribute names.
    If is_json is None, then the current format is detected.
    """
    return (
        _xattr_json
        if (is_json if is_json is not None else format_is_json())
        else _xattr_xml
    )
