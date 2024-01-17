import logging
from collections import UserString
from collections.abc import Mapping, Sequence
from datetime import datetime
from itertools import chain

import cython
import lxml.etree as ET
from humanize import naturalsize

from app.libc.exceptions_context import raise_for
from app.limits import XML_PARSE_MAX_SIZE

if cython.compiled:
    print(f'{__name__}: 🐇 compiled')

_parser = ET.XMLParser(
    ns_clean=True,
    resolve_entities=False,
    remove_comments=True,
    remove_pis=True,
    collect_ids=False,
    compact=False,
)


class XAttr(UserString):
    """
    Custom str implementation for XML attributes (used by `XMLToDict.unparse`).
    """

    __slots__ = 'data', '_custom_xml'

    def __init__(self, seq: str, custom_xml: str | None = None) -> None:
        super().__init__(seq)
        self._custom_xml = custom_xml

    @property
    def xml(self) -> str:
        """
        Return the XML attribute name.

        If `custom_xml` is set, then it is returned instead of the default.
        """

        return self._custom_xml or self.data


class XMLToDict:
    force_list = frozenset(
        (
            'create',
            'modify',
            'delete',
            'node',
            'way',
            'relation',
            'member',
            'tag',
            'nd',
            'trk',
            'trkseg',
            'trkpt',
            'preference',
        )
    )

    value_postprocessor = {  # noqa: RUF012
        '@changeset': int,
        '@closed_at': datetime.fromisoformat,
        '@comments_count': int,
        '@created_at': datetime.fromisoformat,
        '@id': int,
        '@lat': float,
        '@lon': float,
        '@max_lat': float,
        '@max_lon': float,
        '@min_lat': float,
        '@min_lon': float,
        '@num_changes': int,
        '@open': lambda x: x == 'true',
        '@ref': int,
        '@timestamp': datetime.fromisoformat,
        '@uid': int,
        '@version': lambda x: int(x) if x.isdigit() else float(x),
        '@visible': lambda x: x == 'true',
    }

    @staticmethod
    def parse(xml_bytes: bytes, *, sequence: cython.char = False) -> dict:
        """
        Parse XML string to dict.

        If `sequence` is `True`, then the root element is parsed as a sequence.
        """

        if len(xml_bytes) > XML_PARSE_MAX_SIZE:
            raise_for().input_too_big(len(xml_bytes))

        logging.debug('Parsing %s XML string', naturalsize(len(xml_bytes), True))
        root = ET.fromstring(xml_bytes, parser=_parser)  # noqa: S320
        return {_strip_namespace(root.tag): _parse_element(sequence, root, is_root=True)}

    @staticmethod
    def unparse(d: Mapping, *, raw: cython.char = False) -> str | bytes:
        """
        Unparse dict to XML string.

        If `raw` is `True`, then the result is returned as raw bytes.
        """

        # TODO: ensure valid XML charset (encode if necessary) /user/小智智/traces/10908782

        if len(d) != 1:
            raise ValueError(f'Invalid root element count {len(d)}')

        root_k, root_v = next(iter(d.items()))
        elements = _unparse_element(root_k, root_v)

        # always return root element, even if it's empty
        if not elements:
            elements = (ET.Element(root_k),)

        result: bytes = ET.tostring(elements[0], encoding='UTF-8', xml_declaration=True)
        logging.debug('Unparsed %s XML string', naturalsize(len(result), True))

        if raw:
            return result
        else:
            return result.decode()


# read property once for performance
_force_list = XMLToDict.force_list
_value_postprocessor = XMLToDict.value_postprocessor


@cython.cfunc
def _parse_element(sequence: cython.char, element: ET.ElementBase, *, is_root: cython.char):
    parsed = [None] * len(element.attrib)
    is_sequence_and_root: cython.char = sequence and is_root
    i: cython.int

    for i, (k, v) in enumerate(element.attrib.items()):
        k = '@' + k
        v = _postprocessor(k, v)
        parsed[i] = (k, v)

    parsed_children = {}

    for child in element:
        k = _strip_namespace(child.tag)
        v = _parse_element(sequence, child, is_root=False)
        v = _postprocessor(k, v)

        # in sequence mode, return root element as typle
        if is_sequence_and_root:
            parsed.append((k, v))

        # merge with existing value
        elif parsed_v := parsed_children.get(k):
            if isinstance(parsed_v, list):
                parsed_v.append(v)
            else:
                # upgrade from single value to list
                parsed_children[k] = [parsed_v, v]

        # add new value
        else:
            if k in _force_list:
                parsed_children[k] = [v]
            else:
                parsed_children[k] = v

    if parsed_children:
        parsed.extend(parsed_children.items())

    if text := (element.text.strip() if element.text else ''):
        if parsed:
            parsed.append(('#text', text))
        else:
            return text

    if is_sequence_and_root:
        # in sequence mode, return root element as typle
        return parsed
    else:
        return dict(parsed)


@cython.cfunc
def _strip_namespace(tag: str) -> str:
    return tag.rpartition('}')[-1]


@cython.cfunc
def _postprocessor(key: str, value):
    if call := _value_postprocessor.get(key):
        return call(value)
    else:
        return value


@cython.cfunc
def _unparse_element(key, value) -> tuple[ET.ElementBase, ...]:
    if isinstance(value, Mapping):
        element = ET.Element(key)
        for k, v in value.items():
            if k and k[0] == '@':
                element.attrib[k[1:]] = _to_string(v)
            elif isinstance(k, XAttr):
                element.attrib[k.xml] = _to_string(v)
            else:
                element.extend(_unparse_element(k, v))
        return (element,)

    elif isinstance(value, Sequence) and not isinstance(value, str):
        if value:
            first = value[0]
            if isinstance(first, Mapping):
                return tuple(chain.from_iterable(_unparse_element(key, v) for v in value))
            elif isinstance(first, Sequence) and not isinstance(first, str):
                element = ET.Element(key)
                for k, v in value:
                    if k and k[0] == '@':
                        element.attrib[k[1:]] = _to_string(v)
                    elif isinstance(k, XAttr):
                        element.attrib[k.xml] = _to_string(v)
                    else:
                        element.extend(_unparse_element(k, v))
                return (element,)
            else:
                raise ValueError(f'Invalid list item type {type(first)}')
        else:
            return ()

    else:
        element = ET.Element(key)
        element.text = _to_string(value)
        return (element,)


@cython.cfunc
def _to_string(v) -> str:
    if isinstance(v, str | ET.CDATA):
        return v
    elif isinstance(v, datetime):
        return v.isoformat(timespec='seconds') + 'Z'
    elif isinstance(v, bool):
        return 'true' if v else 'false'
    else:
        return str(v)
