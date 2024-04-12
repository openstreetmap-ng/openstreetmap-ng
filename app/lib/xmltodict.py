import logging
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

import cython
import lxml.etree as ET

from app.lib.exceptions_context import raise_for
from app.lib.format_style_context import format_is_json
from app.lib.naturalsize import naturalsize
from app.limits import XML_PARSE_MAX_SIZE


def _xattr_json(name: str, xml: str | None = None) -> str:
    return name


def _xattr_xml(name: str, xml: str | None = None) -> str:
    return f'@{xml}' if (xml is not None) else f'@{name}'


def get_xattr(*, is_json: bool | None = None):
    """
    Return a function to format attribute names.

    If `is_json` is None (default), then the current format is detected.
    """
    if is_json is None:
        is_json = format_is_json()

    return _xattr_json if (is_json is True) else _xattr_xml


@cython.cfunc
def _parse_xml_bool(value: str) -> cython.char:
    return value == 'true'


@cython.cfunc
def _parse_xml_version(value: str):
    # for simplicity, we don't support floating point versions
    return int(value) if value.isdigit() else float(value)


force_sequence_root = {
    'create',
    'modify',
    'delete',
    'node',
    'way',
    'relation',
}

force_list = {
    'member',
    'tag',
    'nd',
    'trk',
    'trkseg',
    'trkpt',
    'preference',
    'comment',
}

value_postprocessor: dict[str, Callable[[str], Any]] = {
    '@changeset': int,
    '@changes_count': int,
    '@closed_at': datetime.fromisoformat,
    '@comments_count': int,
    '@created_at': datetime.fromisoformat,
    '@date': datetime.fromisoformat,
    '@id': int,
    '@lat': float,
    '@lon': float,
    '@max_lat': float,
    '@max_lon': float,
    '@min_lat': float,
    '@min_lon': float,
    '@num_changes': int,
    '@open': _parse_xml_bool,
    '@pending': _parse_xml_bool,
    '@ref': int,
    '@timestamp': datetime.fromisoformat,
    '@uid': int,
    '@updated_at': datetime.fromisoformat,
    '@version': _parse_xml_version,
    '@visible': _parse_xml_bool,
}

_parser = ET.XMLParser(
    ns_clean=True,
    resolve_entities=False,
    remove_comments=True,
    remove_pis=True,
    collect_ids=False,
    compact=False,
)


class XMLToDict:
    @staticmethod
    def parse(xml_bytes: bytes) -> dict:
        """
        Parse XML string to dict.

        If `sequence` is `True`, then the root element is parsed as a sequence.
        """

        if len(xml_bytes) > XML_PARSE_MAX_SIZE:
            raise_for().input_too_big(len(xml_bytes))

        logging.debug('Parsing %s XML string', naturalsize(len(xml_bytes)))
        root = ET.fromstring(xml_bytes, parser=_parser)  # noqa: S320
        return {_strip_namespace(root.tag): _parse_element(root)}

    @staticmethod
    def unparse(d: dict[str, Any], *, raw: bool = False) -> str | bytes:
        """
        Unparse dict to XML string.

        If `raw` is `True`, then the result is returned as raw bytes.
        """

        # TODO: ensure valid XML charset (encode if necessary) /user/小智智/traces/10908782

        if len(d) != 1:
            raise ValueError(f'Invalid root element count {len(d)}')

        root_k: str
        root_v: Any
        root_k, root_v = next(iter(d.items()))
        elements = _unparse_element(root_k, root_v)

        # always return the root element, even if it's empty
        if not elements:
            elements = (ET.Element(root_k.encode()),)

        result: bytes = ET.tostring(elements[0], encoding='UTF-8', xml_declaration=True)
        logging.debug('Unparsed %s XML string', naturalsize(len(result)))

        if raw:
            return result
        else:
            return result.decode()


@cython.cfunc
def _parse_element(element: ET.ElementBase):
    # read property once for performance
    force_sequence_root_: set[str] = force_sequence_root
    force_list_: set[str] = force_list
    value_postprocessor_: dict[str, Callable[[str], Any]] = value_postprocessor
    element_attrib: ET._Attrib = element.attrib

    parsed: list[tuple] = []
    sequence_mark: cython.char = False

    # parse attributes
    k: str
    v: Any
    v_str: str
    for k, v_str in element_attrib.items():
        k = '@' + k

        # post-process value
        call = value_postprocessor_.get(k)
        if call is not None:
            parsed.append((k, call(v_str)))
        else:
            parsed.append((k, v_str))

    # parse children
    parsed_children: dict[str, Any | list[Any]] = {}

    for child in element:
        k = _strip_namespace(child.tag)
        v = _parse_element(child)

        # in sequence mode, return root element as tuple
        if k in force_sequence_root_:
            parsed.append((k, v))
            sequence_mark = True

        # merge with existing value
        elif (parsed_v := parsed_children.get(k)) is not None:
            if isinstance(parsed_v, list):
                parsed_v.append(v)
            else:
                # upgrade from single value to list
                parsed_children[k] = [parsed_v, v]

        # add new value
        else:
            if k in force_list_:
                parsed_children[k] = [v]
            else:
                parsed_children[k] = v

    if parsed_children:
        parsed.extend(parsed_children.items())

    # parse text content
    element_text: str | None = element.text
    if (element_text is not None) and (element_text := element_text.strip()):
        if parsed:
            parsed.append(('#text', element_text))
        else:
            return element_text

    # in sequence mode, return elements as-is: tuple
    if sequence_mark:
        return parsed
    else:
        return dict(parsed)


@cython.cfunc
def _strip_namespace(tag: str) -> str:
    return tag.rpartition('}')[2]


@cython.cfunc
def _unparse_element(key: str, value: Any) -> tuple[ET.ElementBase, ...]:
    # encode dict
    if isinstance(value, dict):
        element = ET.Element(key.encode())
        element_attrib: ET._Attrib = element.attrib  # read property once for performance

        k: str
        v: Any
        for k, v in value.items():
            if k and k[0] == '@':
                element_attrib[k[1:]] = _to_string(v)
            elif k == '#text':
                element.text = _to_string(v)
            else:
                element.extend(_unparse_element(k, v))

        return (element,)

    # encode sequence of ...
    elif isinstance(value, Sequence) and not isinstance(value, str):
        if not value:
            return ()

        first = value[0]

        # encode sequence of dicts
        if isinstance(first, dict):
            result = []
            for v in value:
                result.extend(_unparse_element(key, v))
            return tuple(result)

        # encode sequence of (key, value) tuples
        elif isinstance(first, Sequence) and not isinstance(first, str):
            element = ET.Element(key.encode())
            element_attrib: dict = element.attrib  # read property once for performance

            k: str
            v: Any
            for k, v in value:
                if k and k[0] == '@':
                    element_attrib[k[1:]] = _to_string(v)
                elif k == '#text':
                    element.text = _to_string(v)
                else:
                    element.extend(_unparse_element(k, v))

            return (element,)

        # encode sequence of scalars
        else:
            key_bytes = key.encode()
            result = []
            for v in value:
                element = ET.Element(key_bytes)
                element.text = _to_string(v)
                result.append(element)
            return tuple(result)

    # encode scalar
    else:
        element = ET.Element(key.encode())
        element.text = _to_string(value)
        return (element,)


@cython.cfunc
def _to_string(v) -> str:
    if isinstance(v, str | ET.CDATA):
        return v
    elif isinstance(v, datetime):
        # strip timezone for backwards-compatible format
        tzinfo = v.tzinfo
        if tzinfo is not None:
            if tzinfo is not UTC:
                raise AssertionError(f'Unexpected non-UTC timezone {tzinfo!r}')
            v = v.replace(tzinfo=None)
        return v.isoformat() + 'Z'
    elif isinstance(v, bool):
        return 'true' if (v is True) else 'false'
    else:
        return str(v)
