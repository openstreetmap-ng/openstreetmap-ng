from typing import Literal, TypeAlias, cast, get_args

from app.models.proto.shared_pb2 import RoutingResult
from fastapi import HTTPException
from shapely import Point, get_coordinates
from starlette import status

from app.config import GRAPHHOPPER_API_KEY, GRAPHHOPPER_URL
from app.lib.http_client import HTTP
from app.lib.translation import primary_translation_locale
from app.models.graphhopper import GraphHopperResponse

GraphHopperProfile: TypeAlias = Literal['car', 'bike', 'foot']  # noqa: UP040
GraphHopperProfiles = frozenset[GraphHopperProfile](get_args(GraphHopperProfile))


class GraphHopperQuery:
    @staticmethod
    async def route(start: Point, end: Point, *, profile: GraphHopperProfile):
        if not len(GRAPHHOPPER_API_KEY):
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                'GraphHopper API key is not configured',
            )

        start_x, start_y = get_coordinates(start)[0].tolist()
        end_x, end_y = get_coordinates(end)[0].tolist()
        r = await HTTP.request(
            'POST',
            f'{GRAPHHOPPER_URL}/api/1/route',
            params={'key': GRAPHHOPPER_API_KEY.get_secret_value()},
            json={
                'profile': profile,
                'points': (
                    (start_x, start_y),
                    (end_x, end_y),
                ),
                'locale': primary_translation_locale(),
            },
        )
        content_type: str = r.headers.get('Content-Type', '')
        if not content_type.startswith('application/json'):
            raise HTTPException(r.status_code, r.text)

        data = r.json()
        if not r.is_success:
            if 'message' in data:
                raise HTTPException(r.status_code, data['message'])
            raise HTTPException(r.status_code, r.text)

        path = cast(GraphHopperResponse, data)['paths'][0]
        result = RoutingResult(line_quality=5, line=path['points'])
        result.attribution.href = 'https://www.graphhopper.com'
        result.attribution.label = 'GraphHopper'
        result.elevation.ascend = path['ascend']
        result.elevation.descend = path['descend']

        for instr in path['instructions']:
            step = result.steps.add()
            step.num_coords = instr['interval'][1] - instr['interval'][0] + 1
            step.distance = instr['distance']
            step.duration_seconds = instr['time'] / 1000
            step.icon_num = _SIGN_TO_ICON_MAP.get(instr['sign'], 0)
            step.text = instr['text']

        return result


_SIGN_TO_ICON_MAP = {
    -98: 4,  # U-turn
    -8: 4,  # left U-turn
    -7: 19,  # keep left
    -6: 11,  # leave roundabout
    -3: 7,  # sharp left
    -2: 6,  # left
    -1: 5,  # slight left
    0: 0,  # straight
    1: 1,  # slight right
    2: 2,  # right
    3: 3,  # sharp right
    4: 14,  # finish reached
    5: 14,  # via reached
    6: 10,  # roundabout
    7: 18,  # keep right
    8: 4,  # right U-turn
}
