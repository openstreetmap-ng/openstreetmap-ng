from collections.abc import Sequence
from datetime import datetime

from shapely import Point

from app.format06.geometry_mixin import Geometry06Mixin
from app.libc.auth_context import auth_user
from app.models.db.trace_ import Trace
from app.models.db.trace_point import TracePoint
from app.models.trace_visibility import TraceVisibility
from app.models.validating.trace_ import TraceValidating
from app.models.validating.trace_point import TracePointValidating


class Trace06Mixin:
    @staticmethod
    def encode_track(trace_points: Sequence[TracePoint]) -> dict:
        """
        >>> encode_track([
        ...     TracePoint(...),
        ...     TracePoint(...),
        ... ])
        {'trk': [{'trkseg': [{'trkpt': [{'@lon': 1, '@lat': 2}, {'@lon': 3, '@lat': 4}]}]}]}
        """

        trks = []
        trk_trksegs = []
        trk_trkseg_trkpts = []

        last_trk_id: int | None = None
        last_trkseg_id: int | None = None

        for tp in trace_points:
            trace = tp.trace

            # if trace is available via api, encode full information
            if trace.timestamps_via_api:
                # handle track change
                if last_trk_id != trace.id:
                    if trace.visibility == TraceVisibility.identifiable:
                        url = f'/user/permalink/{trace.user_id}/traces/{trace.id}'
                    else:
                        url = None

                    trk_trksegs = []
                    trks.append(
                        {
                            'name': trace.name,
                            'desc': trace.description,
                            **({'url': url} if url else {}),
                            'trkseg': trk_trksegs,
                        }
                    )
                    last_trk_id = trace.id
                    last_trkseg_id = None

                # handle track segment change
                if last_trkseg_id != tp.track_idx:
                    trk_trkseg_trkpts = []
                    trk_trksegs.append({'trkpt': trk_trkseg_trkpts})
                    last_trkseg_id = tp.track_idx

                # add point
                trk_trkseg_trkpts.append(
                    {
                        **Geometry06Mixin.encode_point(tp.point),
                        **({'ele': tp.elevation} if tp.elevation is not None else {}),
                        'time': tp.captured_at,
                    }
                )

            # otherwise, encode only coordinates
            else:
                # handle track and track segment change
                if last_trk_id is not None or last_trkseg_id is not None:
                    trk_trksegs = []
                    trks.append({'trkseg': trk_trksegs})
                    trk_trkseg_trkpts = []
                    trk_trksegs.append({'trkpt': trk_trkseg_trkpts})
                    last_trk_id = None
                    last_trkseg_id = None

                trk_trkseg_trkpts.append(Geometry06Mixin.encode_point(tp.point))

        return {'trk': trks}

    @staticmethod
    def decode_tracks(tracks: Sequence[dict], *, track_idx_start: int = 0) -> Sequence[TracePoint]:
        """
        >>> decode_tracks([{'trkseg': [{'trkpt': [{'@lon': 1, '@lat': 2}]}]}])
        [TracePoint(...)]
        """

        result = []

        for trk in tracks:
            trk: dict
            for track_idx, trkseg in enumerate(trk.get('trkseg', []), track_idx_start):
                trkseg: dict
                for trkpt in trkseg.get('trkpt', []):
                    trkpt: dict

                    result.append(
                        TracePoint(
                            **TracePointValidating(
                                track_idx=track_idx,
                                captured_at=datetime.fromisoformat(time) if (time := trkpt.get('time')) else None,
                                point=Geometry06Mixin.decode_point_unsafe(trkpt),
                                elevation=trkpt.get('ele'),
                            ).to_orm_dict()
                        )
                    )

        return result

    @staticmethod
    def encode_gpx_file(trace: Trace) -> dict:
        """
        >>> encode_gpx_file(Trace(...))
        {'gpx_file': {'@id': 1, '@uid': 1234, ...}}
        """

        return {
            'gpx_file': {
                '@id': trace.id,
                '@uid': trace.user_id,
                '@user': trace.user.display_name,
                '@timestamp': trace.created_at,
                '@name': trace.name,
                '@lon': trace.start_point.x,
                '@lat': trace.start_point.y,
                '@visibility': trace.visibility.value,
                '@pending': False,
                'description': trace.description,
                'tag': trace.tags,
            }
        }

    @staticmethod
    def encode_gpx_files(traces: Sequence[Trace]) -> dict:
        """
        >>> encode_gpx_files([
        ...     Trace(...),
        ...     Trace(...),
        ... ])
        {'gpx_file': [{'@id': 1, '@uid': 1234, ...}, {'@id': 2, '@uid': 1234, ...}]}
        """

        return {'gpx_file': tuple(Trace06Mixin.encode_gpx_file(trace) for trace in traces)}

    @staticmethod
    def decode_gpx_file(gpx_file: dict) -> Trace:
        return Trace(
            **TraceValidating(
                user_id=auth_user().id,
                name=gpx_file.get('@name'),
                description=gpx_file.get('description'),
                visibility=TraceVisibility(gpx_file.get('@visibility')),
                size=1,
                start_point=Point(0, 0),
                tags=gpx_file.get('tag', ()),
            ).to_orm_dict()
        )
