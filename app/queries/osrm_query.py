import logging
from functools import cache
from typing import Literal, cast, get_args

import cython
from fastapi import HTTPException
from polyline_rs import decode_latlon, encode_latlon
from shapely import Point, get_coordinates

from app.config import OSRM_URL
from app.lib.translation import t
from app.models.osrm import OSRMResponse, OSRMStep
from app.models.proto.shared_pb2 import RoutingResult
from app.utils import HTTP

OSRMProfile = Literal['car', 'bike', 'foot']
OSRMProfiles: frozenset[OSRMProfile] = frozenset(get_args(OSRMProfile))


class OSRMQuery:
    @staticmethod
    async def route(start: Point, end: Point, *, profile: OSRMProfile) -> RoutingResult:
        start_x, start_y = get_coordinates(start)[0].tolist()
        end_x, end_y = get_coordinates(end)[0].tolist()
        r = await HTTP.get(
            f'{OSRM_URL}/route/v1/{profile}/{start_x},{start_y};{end_x},{end_y}',
            params={
                'steps': 'true',
                'geometries': 'polyline6',
                'overview': 'false',
            },
        )
        content_type: str = r.headers.get('Content-Type', '')
        if not content_type.startswith('application/json'):
            raise HTTPException(r.status_code, r.text)

        data = r.json()
        if not r.is_success:
            if 'message' in data and 'code' in data:
                raise HTTPException(
                    r.status_code, f'{data["message"]} ({data["code"]})'
                )
            raise HTTPException(r.status_code, r.text)

        leg = cast(OSRMResponse, data)['routes'][0]['legs'][0]
        points: list[tuple[float, float]] = []
        routing_steps: list[RoutingResult.Step] = [None] * len(leg['steps'])  # type: ignore

        i: cython.Py_ssize_t
        for i, step in enumerate(leg['steps']):
            step_points = decode_latlon(step['geometry'], 6)
            # extend points without overlap
            points.extend(step_points[1:] if i > 0 else step_points)
            maneuver = step['maneuver']
            maneuver_id = _get_maneuver_id(
                maneuver['type'], maneuver.get('modifier', '')
            )
            routing_steps[i] = RoutingResult.Step(
                num_coords=len(step_points),
                distance=step['distance'],
                time=step['duration'],
                icon_num=_MANEUVER_ID_TO_ICON_MAP.get(maneuver_id, 0),
                text=_get_step_text(step, maneuver_id),
            )

        return RoutingResult(
            attribution='<a href="https://routing.openstreetmap.de/about.html" target="_blank">OSRM (FOSSGIS)</a>',
            steps=routing_steps,
            line_quality=6,
            line=encode_latlon(points, 6),
        )


@cache
def _get_maneuver_id(type: str, modifier: str) -> str:
    if type in {'on ramp', 'off ramp', 'merge', 'end of road', 'fork'}:
        direction = 'left' if 'left' in modifier else 'right'
        return f'{type} {direction}'
    if type in {
        'depart',
        'arrive',
        'rotary',
        'roundabout',
        'exit rotary',
        'exit roundabout',
    }:
        return type
    return f'turn {modifier}'


@cython.cfunc
def _get_step_text(step: OSRMStep, maneuver_id: str) -> str:
    translation = _MANEUVER_ID_TO_TRANSLATION_MAP.get(maneuver_id)
    if translation is None:
        logging.warning('Unsupported OSRM maneuver id %r', maneuver_id)
        return ''

    step_name = step['name']
    step_ref = step.get('ref')
    is_own_name: cython.bint
    if step_name and step_ref is not None:
        name = f'{step_name} ({step_ref})'
        is_own_name = True
    elif step_name:
        name = step_name
        is_own_name = True
    elif step_ref is not None:
        name = step_ref
        is_own_name = True
    else:
        name = t('javascripts.directions.instructions.unnamed')
        is_own_name = False

    if maneuver_id in {'exit rotary', 'exit roundabout'}:
        return t(translation, name=name)

    if maneuver_id in {'rotary', 'roundabout'}:
        exit_num = step['maneuver'].get('exit')
        if exit_num is None:
            return t(f'{translation}_without_exit', name=name)  # noqa: INT001

        if 0 < exit_num <= 10:
            return t(
                f'{translation}_with_exit_ordinal',  # noqa: INT001
                name=name,
                exit=t(_MANEUVER_EXIT_TO_TRANSLATION_MAP[exit_num]),
            )

        return t(f'{translation}_with_exit', name=name, exit=exit_num)  # noqa: INT001

    if maneuver_id in {
        'on ramp left',
        'on ramp right',
        'off ramp left',
        'off ramp right',
    }:
        exits = step.get('exits')
        destinations = step.get('destinations')
        params: dict[str, str] = {}

        if exits is not None and maneuver_id in {'off ramp left', 'off ramp right'}:
            params['exit'] = exits
        if is_own_name:
            params['name'] = name
        if destinations is not None:
            params['directions'] = destinations

        # Perform simple translation if no parameters
        if not params:
            return t(translation)

        with_translation_key = f'{translation}_with_{"_".join(params)}'
        return t(with_translation_key, **params)

    return t(f'{translation}_without_exit', name=name)  # noqa: INT001


_MANEUVER_ID_TO_ICON_MAP = {
    'continue': 0,
    'merge right': 21,
    'merge left': 20,
    'off ramp right': 24,
    'off ramp left': 25,
    'on ramp right': 2,
    'on ramp left': 6,
    'fork right': 18,
    'fork left': 19,
    'end of road right': 22,
    'end of road left': 23,
    'turn straight': 0,
    'turn slight right': 1,
    'turn right': 2,
    'turn sharp right': 3,
    'turn uturn': 4,
    'turn slight left': 5,
    'turn left': 6,
    'turn sharp left': 7,
    'roundabout': 10,
    'rotary': 10,
    'exit roundabout': 11,
    'exit rotary': 11,
    'depart': 8,
    'arrive': 14,
}

_MANEUVER_ID_TO_TRANSLATION_MAP = {
    'continue': 'javascripts.directions.instructions.continue',
    'merge right': 'javascripts.directions.instructions.merge_right',
    'merge left': 'javascripts.directions.instructions.merge_left',
    'off ramp right': 'javascripts.directions.instructions.offramp_right',
    'off ramp left': 'javascripts.directions.instructions.offramp_left',
    'on ramp right': 'javascripts.directions.instructions.onramp_right',
    'on ramp left': 'javascripts.directions.instructions.onramp_left',
    'fork right': 'javascripts.directions.instructions.fork_right',
    'fork left': 'javascripts.directions.instructions.fork_left',
    'end of road right': 'javascripts.directions.instructions.endofroad_right',
    'end of road left': 'javascripts.directions.instructions.endofroad_left',
    'turn straight': 'javascripts.directions.instructions.continue',
    'turn slight right': 'javascripts.directions.instructions.slight_right',
    'turn right': 'javascripts.directions.instructions.turn_right',
    'turn sharp right': 'javascripts.directions.instructions.sharp_right',
    'turn uturn': 'javascripts.directions.instructions.uturn',
    'turn sharp left': 'javascripts.directions.instructions.sharp_left',
    'turn left': 'javascripts.directions.instructions.turn_left',
    'turn slight left': 'javascripts.directions.instructions.slight_left',
    'roundabout': 'javascripts.directions.instructions.roundabout',
    'rotary': 'javascripts.directions.instructions.roundabout',
    'exit roundabout': 'javascripts.directions.instructions.exit_roundabout',
    'exit rotary': 'javascripts.directions.instructions.exit_roundabout',
    'depart': 'javascripts.directions.instructions.start',
    'arrive': 'javascripts.directions.instructions.destination',
}

_MANEUVER_EXIT_TO_TRANSLATION_MAP = [
    '',  # zero case
    'javascripts.directions.instructions.exit_counts.first',
    'javascripts.directions.instructions.exit_counts.second',
    'javascripts.directions.instructions.exit_counts.third',
    'javascripts.directions.instructions.exit_counts.fourth',
    'javascripts.directions.instructions.exit_counts.fifth',
    'javascripts.directions.instructions.exit_counts.sixth',
    'javascripts.directions.instructions.exit_counts.seventh',
    'javascripts.directions.instructions.exit_counts.eighth',
    'javascripts.directions.instructions.exit_counts.ninth',
    'javascripts.directions.instructions.exit_counts.tenth',
]
