import logging
from collections.abc import Iterable, Sequence

import cython
import numpy as np
from polyline_rs import encode_lonlat
from shapely import Point, lib

from app.lib.elements_filter import ElementsFilter
from app.lib.query_features import QueryFeatureResult
from app.models.db.element import Element
from app.models.db.element_member import ElementMember
from app.models.element import ElementId
from app.models.proto.shared_pb2 import RenderElementsData


class LeafletElementMixin:
    @staticmethod
    def encode_elements(
        elements: Iterable[Element],
        *,
        detailed: cython.char,
        areas: cython.char = True,
    ) -> RenderElementsData:
        """
        Format elements into a minimal structure, suitable for map rendering.
        """
        node_id_map: dict[ElementId, Element] = {}
        ways: list[Element] = []
        member_nodes_ids: set[ElementId] = set()
        for element in elements:
            if element.type == 'node':
                node_id_map[element.id] = element
            elif element.type == 'way':
                ways.append(element)

        render_ways: list[RenderElementsData.Way] = []
        for way in ways:
            way_members = way.members
            if way_members is None:
                raise AssertionError('Way members must be set')

            way_id = way.id
            member_nodes_ids.update(member.id for member in way_members)
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
                        way_id,
                        way.version,
                    )
                    continue

                current_segment.append(point)

            is_area = _check_way_area(way.tags, way_members) if areas and len(segments) == 1 else False
            for segment in segments:
                if not segment:
                    continue
                geom = lib.get_coordinates(np.asarray(segment, dtype=object), False, False).tolist()
                line = encode_lonlat(geom, 6)
                render_ways.append(RenderElementsData.Way(id=way_id, line=line, area=is_area))

        encode_nodes = ElementsFilter.filter_nodes_interesting(
            node_id_map.values(), member_nodes_ids, detailed=detailed
        )
        encode_points = tuple(node.point for node in encode_nodes)
        geoms = lib.get_coordinates(np.asarray(encode_points, dtype=object), False, False).tolist()
        render_nodes = tuple(
            RenderElementsData.Node(id=node.id, lon=geom[0], lat=geom[1])
            for node, geom in zip(encode_nodes, geoms, strict=True)
        )
        return RenderElementsData(
            nodes=render_nodes,
            ways=render_ways,
        )

    @staticmethod
    def encode_query_features(results: Iterable[QueryFeatureResult]) -> list[RenderElementsData]:
        """
        Format query features results into a minimal structure, suitable for map rendering.
        """
        encoded: list[RenderElementsData] = []
        for result in results:
            element = result.element
            element_type = element.type
            if element_type == 'node':
                point = result.geoms[0][0]
                render_node = RenderElementsData.Node(id=element.id, lon=point[0], lat=point[1])
                encoded.append(RenderElementsData(nodes=(render_node,)))
            elif element_type == 'way':
                render_way = RenderElementsData.Way(id=element.id, line=encode_lonlat(result.geoms[0], 6))
                encoded.append(RenderElementsData(ways=(render_way,)))
            elif element_type == 'relation':
                nodes: list[RenderElementsData.Node] = []
                ways: list[RenderElementsData.Way] = []
                for geom in result.geoms:
                    if len(geom) == 1:
                        point = geom[0]
                        nodes.append(RenderElementsData.Node(id=element.id, lon=point[0], lat=point[1]))
                    else:
                        ways.append(RenderElementsData.Way(id=element.id, line=encode_lonlat(geom, 6)))
                encoded.append(RenderElementsData(nodes=tuple(nodes), ways=tuple(ways)))
            else:
                raise NotImplementedError(f'Unsupported element type {element_type!r}')
        return encoded


@cython.cfunc
def _check_way_area(tags: dict[str, str], members: Sequence[ElementMember]) -> cython.char:
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
