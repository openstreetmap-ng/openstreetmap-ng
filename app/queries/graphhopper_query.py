from typing import Literal, cast, get_args

from fastapi import HTTPException
from shapely import Point, get_coordinates
from starlette import status

from app.config import GRAPHHOPPER_API_KEY, GRAPHHOPPER_URL
from app.lib.translation import primary_translation_locale
from app.models.graphhopper import GraphHopperResponse
from app.models.proto.shared_pb2 import RoutingResult
from app.utils import HTTP

GraphHopperProfile = Literal['car', 'bike', 'foot']
GraphHopperProfiles: frozenset[GraphHopperProfile] = frozenset(get_args(GraphHopperProfile))

__all__ = ('GraphHopperProfiles',)


class GraphHopperQuery:
    @staticmethod
    async def route(start: Point, end: Point, *, profile: GraphHopperProfile) -> RoutingResult:
        if not GRAPHHOPPER_API_KEY:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, 'GraphHopper API key is not configured')

        start_x, start_y = get_coordinates(start)[0].tolist()
        end_x, end_y = get_coordinates(end)[0].tolist()
        r = await HTTP.post(
            f'{GRAPHHOPPER_URL}/api/1/route',
            params={'key': GRAPHHOPPER_API_KEY},
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
        routing_steps: tuple[RoutingResult.Step, ...] = tuple(
            RoutingResult.Step(
                num_coords=instr['interval'][1] - instr['interval'][0] + 1,
                distance=instr['distance'],
                time=instr['time'] / 1000,
                icon_num=_SIGN_TO_ICON_MAP.get(instr['sign'], 0),
                text=instr['text'],
            )
            for instr in path['instructions']
        )

        return RoutingResult(
            attribution='<a href="https://www.graphhopper.com" target="_blank">GraphHopper</a>',
            steps=routing_steps,
            line_quality=5,
            line=path['points'],
            elevation=RoutingResult.Elevation(
                ascend=path['ascend'],
                descend=path['descend'],
            ),
        )


_SIGN_TO_ICON_MAP = {
    -98: 4,  # u-turn
    -8: 4,  # left u-turn
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
    8: 4,  # right u-turn
}
