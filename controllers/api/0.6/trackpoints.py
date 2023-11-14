from typing import Annotated, Sequence

from fastapi import APIRouter, Query
from pydantic import NonNegativeInt

from geoutils import parse_bbox
from lib.exceptions import exceptions
from lib.format.format06 import Format06
from limits import TRACE_POINT_QUERY_AREA_MAX_SIZE, TRACE_POINT_QUERY_DEFAULT_LIMIT
from models.db.trace_point import TracePoint
from models.str import NonEmptyStr
from responses.osm_response import GPXResponse

router = APIRouter()


@router.get('/trackpoints', response_class=GPXResponse)
@router.get('/trackpoints.xml', response_class=GPXResponse)
@router.get('/trackpoints.gpx', response_class=GPXResponse)
async def trackpoints_read(
    bbox: Annotated[NonEmptyStr, Query()], pageNumber: Annotated[NonNegativeInt, Query(0)]
) -> Sequence[dict]:
    geometry = parse_bbox(bbox)
    if geometry.area > TRACE_POINT_QUERY_AREA_MAX_SIZE:
        exceptions().raise_for_trace_points_query_area_too_big()

    points, _ = await TracePoint.find_many_by_geometry_with_(
        cursor=None,
        geometry=geometry,
        limit=TRACE_POINT_QUERY_DEFAULT_LIMIT,
        legacy_skip=pageNumber * TRACE_POINT_QUERY_DEFAULT_LIMIT,
    )

    return Format06.encode_gpx(points)
