import logging
from typing import Any, Literal, overload

from pydantic import ByteSize
from sizestr import sizestr

from app.config import XML_PARSE_MAX_SIZE
from app.lib.exceptions_context import raise_for
from app.lib.format_style_context import format_is_json
from speedup import xattr_json, xattr_xml, xml_parse, xml_unparse


class XMLToDict:
    @staticmethod
    def parse(
        xml_bytes: bytes, *, size_limit: int | ByteSize | None = XML_PARSE_MAX_SIZE
    ):
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
    def unparse(d: dict[str, Any], *, binary: bool = False):
        """Unparse dict to XML string."""
        result = xml_unparse(d, binary)
        logging.debug('Unparsed %s XML string', sizestr(len(result)))
        return result


def get_xattr(*, is_json: bool | None = None):
    """
    Return a function to format attribute names.
    If is_json is None, then the current format is detected.
    """
    return (
        xattr_json
        if (is_json if is_json is not None else format_is_json())
        else xattr_xml
    )
