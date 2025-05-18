import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol, overload

import cython
from lxml.etree import CDATA, XMLParser, tostring
from sizestr import sizestr

from app.config import XML_PARSE_MAX_SIZE
from app.lib.exceptions_context import raise_for
from app.lib.format_style_context import format_is_json
from xmltodict.lib import parse

if TYPE_CHECKING:
    from lxml.etree import _Element

_PARSER = XMLParser(
    remove_blank_text=True,
    remove_comments=True,
    remove_pis=True,
    collect_ids=False,
    resolve_entities=False,
)


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
            return parse(xml_bytes)
        except ValueError as e:
            raise_for.bad_xml('data', str(e), xml_bytes)

    @staticmethod
    @overload
    def unparse(d: dict[str, Any]) -> str: ...
    @staticmethod
    @overload
    def unparse(d: dict[str, Any], *, raw: Literal[True]) -> bytes: ...
    @staticmethod
    @overload
    def unparse(d: dict[str, Any], *, raw: Literal[False]) -> str: ...
    @staticmethod
    def unparse(d: dict[str, Any], *, raw: bool = False) -> str | bytes:
        """Unparse dict to XML string."""
        if len(d) != 1:
            raise ValueError(f'Invalid root element count {len(d)}')

        k, v = next(iter(d.items()))
        dummy = _PARSER.makeelement('dummy')
        _unparse_element(dummy, k, v, {})
        root = e if (e := next(iter(dummy), None)) is not None else dummy.makeelement(k)

        result = tostring(root, encoding='UTF-8', xml_declaration=True)
        logging.debug('Unparsed %s XML string', sizestr(len(result)))
        return result if raw else result.decode()


@cython.cfunc
def _to_string(
    v: Any,
    *,
    datetime=datetime,
    UTC=UTC,  # noqa: N803
    CDATA=CDATA,  # noqa: N803
):
    if v is True:
        return 'true'
    if v is False:
        return 'false'
    if v is None:
        return ''

    t = type(v)

    if t is str or t is CDATA:
        return v

    if t is datetime:
        # strip timezone for backwards-compatible format
        tzinfo = v.tzinfo
        if tzinfo is not None:
            assert tzinfo is UTC, f'Timezone must be UTC, got {tzinfo!r}'
            v = v.replace(tzinfo=None)
        return v.isoformat() + 'Z'

    return str(v)


@cython.cfunc
def _unparse_scalar(parent: '_Element', key: str, value: Any):
    element = parent.makeelement(key)
    element.text = _to_string(value)
    parent.append(element)


@cython.cfunc
def _unparse_item(
    element: '_Element',
    k: str,
    v: Any,
    attr: list[tuple[str, str]],
    /,
    attr_cache: dict[str, str],
):
    kc = k[0]
    if kc == '@':
        attr.append((
            (
                k_
                if (k_ := attr_cache.get(k)) is not None
                else attr_cache.setdefault(k, k[1:])
            ),
            _to_string(v),
        ))
    elif kc == '#' and k == '#text':
        element.text = _to_string(v)
    else:
        _unparse_element(element, k, v, attr_cache)


@cython.cfunc
def _unparse_dict(
    parent: '_Element',
    key: str,
    value: dict[str, Any],
    /,
    attr_cache: dict[str, str],
):
    element = parent.makeelement(key)
    parent.append(element)
    attr: list[tuple[str, str]] = []

    for k, v in value.items():
        _unparse_item(element, k, v, attr, attr_cache)

    if attr:
        element.attrib.update(attr)


@cython.cfunc
def _unparse_element(
    parent: '_Element',
    key: str,
    value: Any,
    /,
    attr_cache: dict[str, str],
):
    t = type(value)

    # Encode dict
    if t is dict:
        _unparse_dict(parent, key, value, attr_cache)

    # Encode sequence of ...
    elif t is list or t is tuple:
        if not value:
            return

        tuples_element: _Element | None = None
        tuples_attr: list[tuple[str, str]] | None = None

        for v in value:
            vt = type(v)

            # ... dicts
            if vt is dict:
                _unparse_dict(parent, key, v, attr_cache)

            # ... (key, value) tuples
            elif vt is tuple or vt is list:
                if tuples_element is None:
                    tuples_element = parent.makeelement(key)
                    tuples_attr = []
                    parent.append(tuples_element)

                k, v = v
                _unparse_item(tuples_element, k, v, tuples_attr, attr_cache)  # type: ignore

            # ... scalars
            else:
                _unparse_scalar(parent, key, v)

        if tuples_attr:
            tuples_element.attrib.update(tuples_attr)  # type: ignore

    # Encode scalar
    else:
        _unparse_scalar(parent, key, value)


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
