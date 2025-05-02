import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol, overload

import cython
from lxml.etree import CDATA, XMLParser, tostring
from sizestr import sizestr

from app.config import XML_PARSE_MAX_SIZE
from app.lib.date_utils import parse_date
from app.lib.exceptions_context import raise_for
from app.lib.format_style_context import format_is_json

if TYPE_CHECKING:
    from lxml.etree import _Element

_PARSER = XMLParser(
    recover=True,
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
        _PARSER.feed(xml_bytes)
        root = _PARSER.close()
        k = _strip_namespace(root.tag)
        v = _parse_element(k, root, {})

        if (t := type(v)) is not dict and t is not list:
            raise_for.bad_xml(k, f'XML contains only text: {v}', xml_bytes)

        return {k: v}  # type: ignore

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


# tags that will become tuples (order-preserving): [('tag', ...), ('tag', ...), ...]
_FORCE_SEQUENCE_ROOT: set[str] = {
    'bounds',
    'create',
    'modify',
    'delete',
    'node',
    'way',
    'relation',
}

# tags that will become a list of values: {'tag': [...]}
_FORCE_LIST: set[str] = {
    'member',
    'tag',
    'nd',
    'trk',
    'trkseg',
    'trkpt',
    'preference',
    'note',
    'comment',
    'gpx_file',
}


@cython.cfunc
def _strip_namespace(tag: str) -> str:
    return tag.rsplit('}', 1)[-1] if tag[0] == '{' else tag


@cython.cfunc
@cython.exceptval(check=False)
def _parse_xml_bool(value: str):
    return value == 'true'


@cython.cfunc
def _parse_xml_version(value: str):
    # for simplicity, we don't support floating-point versions
    return int(value) if '.' not in value else float(value)


@cython.cfunc
def _parse_xml_date(value: str):
    return datetime.fromisoformat(value) if ' ' not in value else parse_date(value)


_VALUE_POSTPROCESSOR: dict[str, Callable[[str], Any]] = {
    'changeset': int,
    'changes_count': int,
    'closed_at': _parse_xml_date,
    'comments_count': int,
    'created_at': _parse_xml_date,
    'date': _parse_xml_date,
    'id': int,
    'lat': float,
    'lon': float,
    'ele': float,
    'max_lat': float,
    'max_lon': float,
    'min_lat': float,
    'min_lon': float,
    'num_changes': int,
    'open': _parse_xml_bool,
    'pending': _parse_xml_bool,
    'ref': int,
    'time': _parse_xml_date,
    'timestamp': _parse_xml_date,
    'uid': int,
    'updated_at': _parse_xml_date,
    'version': _parse_xml_version,
    'visible': _parse_xml_bool,
}


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
def _parse_element(
    element_tag_strip: str,
    element: '_Element',
    /,
    attr_cache: dict[str, str],
    *,
    value_postprocessor: dict[str, Callable[[str], Any]] = _VALUE_POSTPROCESSOR,
    force_sequence_root: set[str] = _FORCE_SEQUENCE_ROOT,
    force_list: set[str] = _FORCE_LIST,
):
    # parse attributes
    parsed: dict[str, Any | list[Any]] = {
        (
            k_
            if (k_ := attr_cache.get(k)) is not None  # type: ignore
            else attr_cache.setdefault(k, '@' + k)  # type: ignore
        ): (
            call(v)  # type: ignore
            if (call := value_postprocessor.get(k)) is not None  # type: ignore
            else v
        )
        for k, v in element.attrib.items()
    }

    # parse children
    parsed_seq: list[tuple[str, Any]] | None = None

    for child in element:
        k = _strip_namespace(child.tag)
        v = _parse_element(k, child, attr_cache)

        # in sequence mode, return root element as list
        if k in force_sequence_root:
            if parsed_seq is not None:
                parsed_seq.append((k, v))
            else:
                parsed_seq = [(k, v)]

        # merge with existing value
        elif (parsed_v := parsed.get(k)) is not None:
            if type(parsed_v) is list:
                parsed_v.append(v)
            else:
                # upgrade from single value to list
                parsed[k] = [parsed_v, v]

        # add new value
        else:
            parsed[k] = [v] if k in force_list else v

    # parse text content
    if (text := element.text) is not None and (text := text.strip()):
        if (call := value_postprocessor.get(element_tag_strip)) is not None:
            text = call(text)
        if not parsed and parsed_seq is None:
            return text
        parsed['#text'] = text

    # in sequence mode, return element as list
    if parsed_seq is None:
        return parsed
    if parsed:
        parsed_seq.extend(parsed.items())
    return parsed_seq


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
