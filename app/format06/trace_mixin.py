from collections.abc import Sequence
from datetime import datetime

import cython
import numpy as np
from shapely import Point, lib

from app.lib.auth_context import auth_user
from app.models.db.trace_ import Trace
from app.models.db.trace_point import TracePoint
from app.validators.trace_ import TraceValidating
from app.validators.trace_point import TracePointValidating


class Trace06Mixin:
    @staticmethod
    def encode_track(trace_points: Sequence[TracePoint], trace_: Trace | None = None) -> dict:
        """
        >>> encode_track([
        ...     TracePoint(...),
        ...     TracePoint(...),
        ... ])
        {'trk': [{'trkseg': [{'trkpt': [{'@lon': 1, '@lat': 2}, {'@lon': 3, '@lat': 4}]}]}]}
        """
        trks: list[dict] = []
        trk_trksegs: list[dict] | None = None
        trk_trkseg_trkpts: list[dict] | None = None

        last_trk_id: cython.int = -1
        last_trkseg_id: cython.int = -1

        for tp in trace_points:
            trace = tp.trace if (trace_ is None) else trace_

            # if trace is available via api, encode full information
            if trace.timestamps_via_api:
                trace_id: cython.int = trace.id
                track_idx: cython.int = tp.track_idx

                # handle track change
                if last_trk_id != trace_id:
                    trk_trksegs = []
                    trks.append(
                        {
                            'name': trace.name,
                            'desc': trace.description,
                            'trkseg': trk_trksegs,
                        }
                    )
                    last_trk_id = trace_id
                    last_trkseg_id = -1

                # handle track segment change
                if last_trkseg_id != track_idx:
                    trk_trkseg_trkpts = []
                    trk_trksegs.append({'trkpt': trk_trkseg_trkpts})
                    last_trkseg_id = track_idx

            # otherwise, encode only coordinates
            else:
                # handle track and track segment change
                if (last_trk_id > -1 or trk_trksegs is None) or (last_trkseg_id > -1 or trk_trkseg_trkpts is None):
                    trk_trksegs = []
                    trks.append({'trkseg': trk_trksegs})
                    trk_trkseg_trkpts = []
                    trk_trksegs.append({'trkpt': trk_trkseg_trkpts})
                    last_trk_id = -1
                    last_trkseg_id = -1

            # add point
            trk_trkseg_trkpts.append(
                {
                    **_encode_point_xml(tp.point),
                    **({'ele': tp.elevation} if (tp.elevation is not None) else {}),
                    'time': tp.captured_at,
                }
            )

        return {'trk': trks}

    @staticmethod
    def decode_tracks(tracks: Sequence[dict], *, track_idx_start: int = 0) -> Sequence[TracePoint]:
        """
        >>> decode_tracks([{'trkseg': [{'trkpt': [{'@lon': 1, '@lat': 2}]}]}])
        [TracePoint(...)]
        """
        result = []

        trk: dict
        trkseg: dict
        trkpt: dict

        for trk in tracks:
            for track_idx, trkseg in enumerate(trk.get('trkseg', ()), track_idx_start):
                for trkpt in trkseg.get('trkpt', ()):
                    if (time := trkpt.get('time')) is not None:
                        captured_at = datetime.fromisoformat(time)
                    else:
                        captured_at = None

                    if (lon := trkpt.get('@lon')) is None or (lat := trkpt.get('@lat')) is None:
                        point = None
                    else:
                        # numpy automatically parses strings
                        point = lib.points(np.array((lon, lat), np.float64))

                    result.append(
                        TracePoint(
                            **dict(
                                TracePointValidating(
                                    track_idx=track_idx,
                                    captured_at=captured_at,
                                    point=point,
                                    elevation=trkpt.get('ele'),
                                )
                            )
                        )
                    )

        return result

    @staticmethod
    def encode_gpx_file(trace: Trace) -> dict:
        """
        >>> encode_gpx_file(Trace(...))
        {'gpx_file': {'@id': 1, '@uid': 1234, ...}}
        """
        return {'gpx_file': _encode_gpx_file(trace)}

    @staticmethod
    def encode_gpx_files(traces: Sequence[Trace]) -> dict:
        """
        >>> encode_gpx_files([
        ...     Trace(...),
        ...     Trace(...),
        ... ])
        {'gpx_file': [{'@id': 1, '@uid': 1234, ...}, {'@id': 2, '@uid': 1234, ...}]}
        """
        return {'gpx_file': tuple(_encode_gpx_file(trace) for trace in traces)}

    @staticmethod
    def decode_gpx_file(gpx_file: dict) -> Trace:
        return Trace(
            **dict(
                TraceValidating(
                    user_id=auth_user().id,
                    name=gpx_file.get('@name'),
                    description=gpx_file.get('description'),
                    visibility=gpx_file.get('@visibility'),
                    size=1,
                    start_point=Point(0, 0),
                    tags=gpx_file.get('tag', ()),
                )
            )
        )


@cython.cfunc
def _encode_gpx_file(trace: Trace) -> dict:
    """
    >>> _encode_gpx_file(Trace(...))
    {'@id': 1, '@uid': 1234, ...}
    """
    x, y = lib.get_coordinates(np.asarray(trace.start_point, dtype=object), False, False)[0].tolist()
    return {
        '@id': trace.id,
        '@uid': trace.user_id,
        '@user': trace.user.display_name,
        '@timestamp': trace.created_at,
        '@name': trace.name,
        '@lon': x,
        '@lat': y,
        '@visibility': trace.visibility,
        '@pending': False,
        'description': trace.description,
        'tag': trace.tags,
    }


@cython.cfunc
def _encode_point_xml(point: Point) -> dict:
    """
    >>> _encode_point_xml(Point(1, 2))
    {'@lon': 1, '@lat': 2}
    """
    x, y = lib.get_coordinates(np.asarray(point, dtype=object), False, False)[0].tolist()
    return {'@lon': x, '@lat': y}
