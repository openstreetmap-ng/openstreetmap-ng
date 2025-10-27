import logging

import cython
from polyline_rs import encode_lonlat
from shapely import Point, get_coordinates, prepare
from shapely.geometry.base import BaseGeometry

from app.lib.elements_filter import ElementsFilter
from app.lib.query_features import QueryFeatureResult
from app.models.db.element import Element
from app.models.element import (
    TYPED_ELEMENT_ID_WAY_MAX,
    TYPED_ELEMENT_ID_WAY_MIN,
    TypedElementId,
)
from app.models.proto.shared_pb2 import RenderElementsData
from speedup.element_type import split_typed_element_id


class LeafletElementMixin:
    @staticmethod
    def encode_elements(
        elements: list[Element],
        *,
        detailed: cython.bint,
        areas: cython.bint = True,
    ) -> RenderElementsData:
        """Format elements into a minimal structure, suitable for map rendering."""
        node_id_map: dict[TypedElementId, Element] = {}
        ways: list[Element] = []
        for element in elements:
            typed_id = element['typed_id']
            type = split_typed_element_id(typed_id)[0]
            if type == 'node':
                node_id_map[typed_id] = element
            elif type == 'way':
                ways.append(element)

        member_nodes = set[TypedElementId]()
        render_ways = _render_ways(
            ways=ways, node_id_map=node_id_map, areas=areas, member_nodes=member_nodes
        )
        render_nodes = _render_nodes(
            node_id_map=node_id_map, member_nodes=member_nodes, detailed=detailed
        )
        return RenderElementsData(
            nodes=render_nodes,
            ways=render_ways,
        )

    @staticmethod
    def encode_query_features(
        results: list[QueryFeatureResult],
        *,
        search_area: BaseGeometry | None = None,
    ) -> list[RenderElementsData]:
        """Format query features results into a minimal structure, suitable for map rendering."""
        if search_area is not None:
            prepare(search_area)
        encoded: list[RenderElementsData] = []

        for result in results:
            if _skip_non_area_polygon(result, search_area):
                continue

            type, id = split_typed_element_id(result.element['typed_id'])
            sequences = _geometry_to_sequences(result.geometry)

            if type == 'node':
                point = sequences[0][0]
                render_node = RenderElementsData.Node(id=id, lon=point[0], lat=point[1])
                encoded.append(RenderElementsData(nodes=[render_node]))

            elif type == 'way':
                render_way = RenderElementsData.Way(
                    id=id, line=encode_lonlat(sequences[0], 6)
                )
                encoded.append(RenderElementsData(ways=[render_way]))

            elif type == 'relation':
                nodes: list[RenderElementsData.Node] = []
                ways: list[RenderElementsData.Way] = []
                for seq in sequences:
                    if len(seq) == 1:
                        point = seq[0]
                        nodes.append(
                            RenderElementsData.Node(id=id, lon=point[0], lat=point[1])
                        )
                    else:
                        ways.append(
                            RenderElementsData.Way(id=id, line=encode_lonlat(seq, 6))
                        )
                encoded.append(RenderElementsData(nodes=nodes, ways=ways))

            else:
                raise NotImplementedError(f'Unsupported element type {type!r}')

        return encoded


@cython.cfunc
def _render_ways(
    *,
    ways: list[Element],
    node_id_map: dict[TypedElementId, Element],
    areas: cython.bint,
    member_nodes: set[TypedElementId],
) -> list[RenderElementsData.Way]:
    result: list[RenderElementsData.Way] = []

    for way in ways:
        way_members = way['members']
        if not way_members:
            continue

        member_nodes.update(way_members)
        way_id = split_typed_element_id(way['typed_id'])[1]
        segments: list[list[Point]] = []
        current_segment: list[Point] = []

        for node_ref in way_members:
            node = node_id_map.get(node_ref)
            if node is None:
                # split way on gap
                if current_segment:
                    segments.append(current_segment)
                    current_segment = []
                continue

            point = node['point']
            if point is None:
                logging.warning(
                    'Missing point for node %d version %d (part of way %d version %d)',
                    node['typed_id'],
                    node['version'],
                    way_id,
                    way['version'],
                )
                continue

            current_segment.append(point)

        # Finish the segment if non-empty
        if current_segment:
            segments.append(current_segment)

        is_area = (
            _check_way_area(way['tags'], way_members)
            if areas and len(segments) == 1
            else False
        )
        for segment in segments:
            geom: list[list[float]] = get_coordinates(segment).tolist()
            line = encode_lonlat(geom, 6)
            result.append(RenderElementsData.Way(id=way_id, line=line, area=is_area))

    return result


@cython.cfunc
def _render_nodes(
    node_id_map: dict[TypedElementId, Element],
    member_nodes: set[TypedElementId],
    detailed: cython.bint,
) -> list[RenderElementsData.Node]:
    nodes = list(node_id_map.values())
    nodes = ElementsFilter.filter_nodes_interesting(
        nodes, member_nodes, detailed=detailed
    )
    if not nodes:
        return []

    points = [node['point'] for node in nodes]
    geoms: list[list[float]] = get_coordinates(points).tolist()
    return [
        RenderElementsData.Node(id=node['typed_id'], lon=geom[0], lat=geom[1])
        for node, geom in zip(nodes, geoms, strict=True)
    ]


_AREA_TAGS = frozenset[str]((
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
))


@cython.cfunc
def _geometry_to_sequences(geometry: BaseGeometry) -> list[list[list[float]]]:
    gtype: str = geometry.geom_type

    if gtype in {'Point', 'LineString'}:
        return [get_coordinates(geometry).tolist()]

    if gtype in {'Polygon', 'MultiPolygon'}:
        return _geometry_to_sequences(geometry.boundary)

    if gtype in {'MultiPoint', 'MultiLineString', 'GeometryCollection'}:
        out: list[list[list[float]]] = []
        for sub in geometry.geoms:  # type: ignore
            out.extend(_geometry_to_sequences(sub))
        return out

    raise NotImplementedError(f'Unsupported geometry type {gtype!r}')


@cython.cfunc
def _skip_non_area_polygon(
    result: QueryFeatureResult,
    search_area: BaseGeometry | None,
) -> cython.bint:
    return (
        search_area is not None
        and (
            TYPED_ELEMENT_ID_WAY_MIN
            <= result.element['typed_id']
            <= TYPED_ELEMENT_ID_WAY_MAX
        )
        and not _has_area_tag(result.element.get('tags'))
        and search_area.disjoint(result.geometry)
    )


@cython.cfunc
def _check_way_area(
    tags: dict[str, str] | None,
    members: list[TypedElementId],
) -> cython.bint:
    """Check if the way should be displayed as an area."""
    return (
        tags is not None
        and len(members) > 2  # has enough members
        and members[0] == members[-1]  # is closed
        and _has_area_tag(tags)
    )


@cython.cfunc
def _has_area_tag(tags: dict[str, str] | None) -> cython.bint:
    return bool(
        tags
        and (
            _AREA_TAGS.intersection(tags)
            or any(key.startswith('area:') for key in tags)
        )
    )
