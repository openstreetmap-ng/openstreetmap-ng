import logging
from collections.abc import Iterable, Sequence

import cython
import numpy as np
from shapely import Point, lib

from app.models.db.element import Element
from app.models.db.element_member import ElementMember
from app.models.element import ElementId
from app.models.leaflet import (
    ElementLeafletNode,
    ElementLeafletWay,
)


class LeafletElementMixin:
    @staticmethod
    def encode_elements(
        elements: Iterable[Element],
        *,
        detailed: cython.char,
        areas: cython.char = True,
    ) -> list[ElementLeafletNode | ElementLeafletWay]:
        """
        Format elements into a minimal structure, suitable for Leaflet rendering.
        """
        node_id_map: dict[ElementId, Element] = {}
        way_id_map: dict[ElementId, Element] = {}
        way_nodes_ids: set[ElementId] = set()
        result: list[ElementLeafletNode | ElementLeafletWay] = []

        for element in elements:
            if element.type == 'node':
                node_id_map[element.id] = element
            elif element.type == 'way':
                way_id_map[element.id] = element

        for way_id, way in way_id_map.items():
            way_members = way.members
            if way_members is None:
                raise AssertionError('Way members must be set')

            way_nodes_ids.update(member.id for member in way_members)
            current_segment: list[Point] = []
            segments: list[list[Point]] = [current_segment]

            for node_ref in way_members:
                node = node_id_map.get(node_ref.id)
                if node is None:
                    # split way on gap
                    if current_segment:
                        current_segment = []
                        segments.append(current_segment)
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

                current_segment.append(point)

            is_area = _is_way_area(way.tags, way_members) if areas and len(segments) == 1 else False
            for segment in segments:
                if not segment:
                    continue
                geom = np.fliplr(lib.get_coordinates(np.asarray(segment, dtype=object), False, False)).tolist()
                result.append(ElementLeafletWay('way', way_id, geom, is_area))

        encode_nodes = tuple(
            node
            for node in node_id_map.values()
            if _is_node_interesting(node, way_nodes_ids, detailed=detailed) and node.point is not None
        )
        encode_points = tuple(node.point for node in encode_nodes)
        geoms = np.fliplr(lib.get_coordinates(np.asarray(encode_points, dtype=object), False, False)).tolist()
        result.extend(ElementLeafletNode('node', node.id, geom) for node, geom in zip(encode_nodes, geoms, strict=True))
        return result


@cython.cfunc
def _is_way_area(tags: dict[str, str], members: Sequence[ElementMember]) -> cython.char:
    """
    Check if the way should be displayed as an area.
    """
    if len(members) <= 2:
        return False
    is_closed = members[0].id == members[-1].id
    if not is_closed:
        return False
    area_tags = _area_tags.intersection(tags)
    if area_tags:
        return True
    return any(key.startswith(_area_prefixes) for key in tags)


@cython.cfunc
def _is_node_interesting(node: Element, way_nodes_ids: set[ElementId], *, detailed: cython.char) -> cython.char:
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
        'amenity',
        'area',
        'building',
        'building:part',
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

_area_prefixes: tuple[str, ...] = ('area:',)
