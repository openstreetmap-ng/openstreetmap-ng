import logging
import xml.etree.ElementTree as ET
from abc import ABC
from collections import UserString
from datetime import datetime
from itertools import chain
from typing import Any, Sequence

from humanize import naturalsize

from lib.exceptions import Exceptions
from limits import XML_PARSE_MAX_SIZE


class XAttr(UserString):
    '''
    Custom str implementation for XML attributes.
    '''

    def __init__(self, seq: str, custom_xml: str | None = None) -> None:
        super().__init__(seq)
        self.custom_xml = custom_xml


    @property
    def xml(self) -> str:
        '''
        Return the XML attribute name.

        If `custom_xml` is set, then it is returned instead of the default.
        '''

        return self.custom_xml or self.data


class XMLToDict(ABC):
    force_list = frozenset((
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
    ))
    postprocessor_d = {
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
    def parse(xml_str: str, *, sequence: bool = False) -> dict:
        '''
        Parse XML string to dict.

        If `sequence` is `True`, then the root element is parsed as a sequence.
        '''

        def parse_element(element: ET.Element, path='') -> dict | Sequence[dict] | str:
            postprocessor = XMLToDict.postprocessor
            parsed = [None] * len(element.attrib)

            for i, (k, v) in enumerate(element.attrib.items()):
                k = '@' + k
                k, v = postprocessor(path, k, v)
                parsed[i] = (k, v)

            parsed_children = {}

            for child in element:
                v = parse_element(child, '/'.join((path, _strip_namespace(element.tag))))
                k, v = postprocessor(path, _strip_namespace(child.tag), v)

                if sequence and not path:
                    parsed.append((k, v))
                else:
                    if parsed_v := parsed_children.get(k):
                        if isinstance(parsed_v, list):
                            parsed_v.append(v)
                        else:
                            parsed_children[k] = [parsed_v, v]
                    else:
                        if k in XMLToDict.force_list:
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

            if sequence and not path:
                return parsed
            else:
                return dict(parsed)

        if len(xml_str) > XML_PARSE_MAX_SIZE:
            Exceptions.get().raise_for_input_too_big(len(xml_str))

        logging.debug('Parsing %s XML string', naturalsize(len(xml_str), True))
        root = ET.fromstring(xml_str)
        return {_strip_namespace(root.tag): parse_element(root)}

    @staticmethod
    def unparse(d: dict, *, raw: bool = False) -> str | bytes:
        '''
        Unparse dict to XML string.

        If `raw` is `True`, then the result is returned as raw bytes.
        '''

        # TODO: ensure valid XML charset (encode if necessary) /user/小智智/traces/10908782

        def create_element(key, value) -> Sequence[ET.Element]:
            if isinstance(value, dict):
                element = ET.Element(key)
                for k, v in value.items():
                    if k.startswith('@'):
                        element.attrib[k[1:]] = _to_string(v)
                    elif isinstance(k, XAttr):
                        element.attrib[k.xml] = _to_string(v)
                    else:
                        element.extend(create_element(k, v))
                return (element,)
            elif isinstance(value, (list, tuple)):
                if value:
                    first = value[0]
                    if isinstance(first, dict):
                        return tuple(chain.from_iterable(create_element(key, v) for v in value))
                    elif isinstance(first, (list, tuple)):
                        element = ET.Element(key)
                        for k, v in value:
                            if k.startswith('@'):
                                element.attrib[k[1:]] = _to_string(v)
                            elif isinstance(k, XAttr):
                                element.attrib[k.xml] = _to_string(v)
                            else:
                                element.extend(create_element(k, v))
                        return (element,)
                    else:
                        raise ValueError(f'Invalid list item type {type(first)}')
                else:
                    return ()
            else:
                element = ET.Element(key)
                element.text = str(value)
                return (element,)

        if len(d) != 1:
            raise ValueError(f'Invalid root element count {len(d)}')

        root_k, root_v = next(iter(d.items()))
        result: bytes = ET.tostring(create_element(root_k, root_v)[0], encoding='UTF-8', xml_declaration=True)
        logging.debug('Unparsed %s XML string', naturalsize(len(result), True))

        if raw:
            return result
        else:
            return result.decode()

    @staticmethod
    def postprocessor(path, key: str, value):
        if call := XMLToDict.postprocessor_d.get(key):
            return key, call(value)
        else:
            return key, value



def _strip_namespace(tag: str) -> str:
    return tag.rpartition('}')[-1]


def _to_string(v: Any) -> str:
    if isinstance(v, bool):
        return 'true' if v else 'false'
    elif isinstance(v, datetime):
        return v.isoformat(timespec='seconds') + 'Z'
    else:
        return str(v)
