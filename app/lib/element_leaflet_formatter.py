import logging
from collections.abc import Sequence

import cython
import numpy as np
from shapely import Point, get_coordinates

from app.models.db.element import Element
from app.models.msgspec.element_leaflet import (
    ElementLeaflet,
    ElementLeafletNode,
    ElementLeafletWay,
)


def format_leaflet_elements(elements: Sequence[Element], *, detailed: cython.char) -> list[ElementLeaflet]:
    """
    Format elements into a minimal structure, suitable for Leaflet rendering.
    """
    node_id_map: dict[int, Element] = {}
    way_id_map: dict[int, Element] = {}
    way_nodes_ids: set[int] = set()
    result: list[ElementLeaflet] = []

    for element in elements:
        if element.type == 'node':
            node_id_map[element.id] = element
        elif element.type == 'way':
            way_id_map[element.id] = element
            way_nodes_ids.update(member.id for member in element.members)

    for way_id, way in way_id_map.items():
        points: list[Point] = []

        for node_ref in way.members:
            node = node_id_map.get(node_ref.id)
            if node is None:
                continue

            point = node.point
            if point is None:
                logging.warning(
                    'Missing point for node %d version %d (part of way %d version %d)',
                    node.id,
                    node.version,
                    way.id,
                    way.version,
                )
                continue

            points.append(point)

        geom = np.fliplr(get_coordinates(points)).tolist()
        area = _is_way_area(way)
        result.append(ElementLeafletWay('way', way_id, geom, area))

    for node_id, node in node_id_map.items():
        if not _is_node_interesting(node, way_nodes_ids, detailed=detailed):
            continue

        point = node.point
        if point is None:
            logging.warning('Missing point for node %d version %d ', node.id, node.version)
            continue

        geom: list[float] = get_coordinates(point)[0][::-1].tolist()
        result.append(ElementLeafletNode('node', node_id, geom))

    return result


@cython.cfunc
def _is_way_area(way: Element) -> cython.char:
    """
    Check if the way should be displayed as an area.
    """
    if len(way.members) <= 2:
        return False

    is_closed = way.members[0].id == way.members[-1].id
    if not is_closed:
        return False

    area_tags = _area_tags.intersection(way.tags)
    if area_tags:
        return True

    for key in way.tags:  # noqa: SIM110
        if key.startswith(_area_tags_prefixes):
            return True

    return False


@cython.cfunc
def _is_node_interesting(node: Element, way_nodes_ids: set[int], *, detailed: cython.char) -> cython.char:
    """
    Check if the node is interesting enough to be displayed.
    """
    is_member: cython.char = node.id in way_nodes_ids
    if not detailed:
        return not is_member
    if not is_member:
        return True
    return bool(node.tags)


_area_tags: frozenset[str] = frozenset(
    (
        'area',
        'building',
        'leisure',
        'tourism',
        'ruins',
        'historic',
        'landuse',
        'military',
        'natural',
        'sport',
    )
)

_area_tags_prefixes: tuple[str, ...] = ('area:',)
