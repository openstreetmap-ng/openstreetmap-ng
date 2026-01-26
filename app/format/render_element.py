import cython
from polyline_rs import encode_lonlat
from shapely import Point, get_coordinates
from shapely.geometry.base import BaseGeometry

from app.lib.elements_filter import ElementsFilter
from app.lib.query_features import QueryFeatureResult
from app.models.db.element import Element
from app.models.element import TypedElementId
from app.models.proto.element_pb2 import RenderElementsData
from app.models.proto.shared_pb2 import LonLat
from speedup import element_id, element_type, split_typed_element_id


class RenderElementMixin:
    @staticmethod
    def encode_elements(
        elements: list[Element],
        *,
        detailed: cython.bint,
        areas: cython.bint = True,
    ):
        """Format elements into a minimal structure, suitable for map rendering."""
        node_id_map: dict[TypedElementId, Element] = {}
        ways: list[Element] = []
        for element in elements:
            typed_id = element['typed_id']
            type = element_type(typed_id)
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
    def encode_query_features(results: list[QueryFeatureResult]):
        """Format query features results into a minimal structure, suitable for map rendering."""
        encoded: list[RenderElementsData] = []

        for result in results:
            type, id = split_typed_element_id(result.element['typed_id'])
            sequences = _geometry_to_sequences(result.geometry)

            if type == 'node':
                point = sequences[0][0]
                render_node = RenderElementsData.Node(
                    id=id, location=LonLat(lon=point[0], lat=point[1])
                )
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
                            RenderElementsData.Node(
                                id=id, location=LonLat(lon=point[0], lat=point[1])
                            )
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
):
    result: list[RenderElementsData.Way] = []

    for way in ways:
        way_members = way['members']
        if not way_members:
            continue

        member_nodes.update(way_members)
        way_id = element_id(way['typed_id'])
        segments: list[list[Point]] = []
        current_segment: list[Point] = []

        for node_ref in way_members:
            node = node_id_map.get(node_ref)
            if node is None or (point := node['point']) is None:
                # split way on gap
                if current_segment:
                    segments.append(current_segment)
                    current_segment = []
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
            result.append(RenderElementsData.Way(id=way_id, line=line, is_area=is_area))

    return result


@cython.cfunc
def _render_nodes(
    node_id_map: dict[TypedElementId, Element],
    member_nodes: set[TypedElementId],
    detailed: cython.bint,
) -> list[RenderElementsData.Node]:
    nodes = ElementsFilter.filter_nodes_interesting(
        node_id_map.values(), member_nodes, detailed=detailed
    )
    if not nodes:
        return []

    points = [node['point'] for node in nodes]
    geoms: list[list[float]] = get_coordinates(points).tolist()
    return [
        RenderElementsData.Node(
            id=node['typed_id'], location=LonLat(lon=geom[0], lat=geom[1])
        )
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
        result: list[list[list[float]]] = []
        for sub in geometry.geoms:  # type: ignore
            result.extend(_geometry_to_sequences(sub))
        return result

    raise NotImplementedError(f'Unsupported geometry type {gtype!r}')


@cython.cfunc
def _check_way_area(
    tags: dict[str, str] | None,
    members: list[TypedElementId],
):
    """Check if the way should be displayed as an area."""
    return (
        tags is not None
        and len(members) > 2  # has enough members
        and members[0] == members[-1]  # is closed
        and _has_area_tag(tags)
    )


@cython.cfunc
def _has_area_tag(
    tags: dict[str, str] | None,
    /,
    *,
    _AREA_TAGS=_AREA_TAGS,
):
    if not tags:
        return False

    for key in tags:
        if key in _AREA_TAGS or key[:5] == 'area:':
            return True

    return False
