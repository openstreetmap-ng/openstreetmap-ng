from typing import Literal, cast, get_args

import cython
import numpy as np
from fastapi import HTTPException
from polyline_rs import decode_latlon, encode_latlon
from shapely import Point, get_coordinates

from app.config import VALHALLA_URL
from app.lib.translation import primary_translation_locale
from app.models.proto.shared_pb2 import RoutingResult
from app.models.valhalla import ValhallaResponse
from app.utils import HTTP

ValhallaProfile = Literal['auto', 'bicycle', 'pedestrian']
ValhallaProfiles: frozenset[ValhallaProfile] = frozenset(get_args(ValhallaProfile))

__all__ = ('ValhallaProfiles',)


class ValhallaQuery:
    @staticmethod
    async def route(start: Point, end: Point, *, profile: ValhallaProfile) -> RoutingResult:
        start_x, start_y = get_coordinates(start)[0].tolist()
        end_x, end_y = get_coordinates(end)[0].tolist()
        r = await HTTP.post(
            f'{VALHALLA_URL}/route',
            json={
                'locations': [
                    {'lon': start_x, 'lat': start_y},
                    {'lon': end_x, 'lat': end_y},
                ],
                'costing': profile,
                'units': 'km',
                'language': primary_translation_locale(),
                'elevation_interval': '30',
            },
        )
        content_type: str = r.headers.get('Content-Type', '')
        if not content_type.startswith('application/json'):
            raise HTTPException(r.status_code, r.text)

        data = r.json()
        if not r.is_success:
            if 'error' in data and 'error_code' in data:
                raise HTTPException(r.status_code, f"{data['error']} ({data['error_code']})")
            raise HTTPException(r.status_code, r.text)

        leg = cast(ValhallaResponse, data)['trip']['legs'][0]
        points = decode_latlon(leg['shape'], 6)
        routing_steps: list[RoutingResult.Step] = [None] * len(leg['maneuvers'])  # type: ignore

        i: cython.int
        for i, maneuver in enumerate(leg['maneuvers']):
            maneuver_points = points[maneuver['begin_shape_index'] : maneuver['end_shape_index'] + 1]
            routing_steps[i] = RoutingResult.Step(
                line=encode_latlon(maneuver_points, 6),
                distance=maneuver['length'] * 1000,
                time=maneuver['time'],
                icon_num=_MANEUVER_TYPE_TO_ICON_MAP.get(maneuver['type'], 0),
                text=maneuver['instruction'],
            )

        elevations = np.diff(np.asarray(leg['elevation'], dtype=np.float32), 1)
        ascend = elevations[elevations > 0].sum()
        descend = -elevations[elevations < 0].sum()
        return RoutingResult(
            attribution='<a href="https://gis-ops.com/global-open-valhalla-server-online/" target="_blank">Valhalla (FOSSGIS)</a>',
            steps=routing_steps,
            elevation=RoutingResult.Elevation(
                ascend=ascend,
                descend=descend,
            ),
        )


_MANEUVER_TYPE_TO_ICON_MAP = {
    0: 0,  # straight
    1: 8,  # start
    2: 8,  # start right
    3: 8,  # start left
    4: 14,  # destination
    5: 14,  # destination right
    6: 14,  # destination left
    7: 0,  # becomes
    8: 0,  # continue
    9: 1,  # slight right
    10: 2,  # right
    11: 3,  # sharp right
    12: 4,  # u-turn right
    13: 4,  # u-turn left
    14: 7,  # sharp left
    15: 6,  # left
    16: 5,  # slight left
    17: 0,  # ramp straight
    18: 24,  # ramp right
    19: 25,  # ramp left
    20: 24,  # exit right
    21: 25,  # exit left
    22: 0,  # stay straight
    23: 1,  # stay right
    24: 5,  # stay left
    25: 20,  # merge
    26: 10,  # roundabout enter
    27: 11,  # roundabout exit
    28: 17,  # ferry enter
    29: 0,  # ferry exit
    37: 21,  # merge right
    38: 20,  # merge left
}
