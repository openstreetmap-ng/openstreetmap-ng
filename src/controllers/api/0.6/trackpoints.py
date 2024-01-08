from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import NonNegativeInt

from src.lib.exceptions import raise_for
from src.lib.format.format06 import Format06
from src.lib_cython.geo_utils import parse_bbox
from src.limits import TRACE_POINT_QUERY_AREA_MAX_SIZE, TRACE_POINT_QUERY_DEFAULT_LIMIT
from src.repositories.trace_point_repository import TracePointRepository
from src.responses.osm_response import GPXResponse

router = APIRouter()


@router.get('/trackpoints', response_class=GPXResponse)
@router.get('/trackpoints.gpx', response_class=GPXResponse)
async def trackpoints_read(
    bbox: Annotated[str, Query(min_length=1)],
    page_number: Annotated[NonNegativeInt, Query(0, alias='pageNumber')],
) -> dict:
    geometry = parse_bbox(bbox)

    if geometry.area > TRACE_POINT_QUERY_AREA_MAX_SIZE:
        raise_for().trace_points_query_area_too_big()

    points = await TracePointRepository.find_many_by_geometry(
        geometry,
        limit=TRACE_POINT_QUERY_DEFAULT_LIMIT,
        legacy_offset=page_number * TRACE_POINT_QUERY_DEFAULT_LIMIT,
    )

    return Format06.encode_tracks(points)
