from datetime import datetime
from typing import Any, NamedTuple

import cython
from shapely import MultiLineString, get_coordinates

from app.lib.exceptions_context import raise_for
from app.models.db.trace import Trace, trace_is_timestamps_via_api


class DecodeTracksResult(NamedTuple):
    size: int
    segments: MultiLineString
    elevations: list[float | None] | None
    capture_times: list[datetime | None] | None


class FormatGPX:
    @staticmethod
    def encode_tracks(traces: list[Trace]) -> dict:
        trk: list[dict] = []

        for trace in traces:
            elevations = trace['elevations']
            elevations_iter = iter(elevations) if elevations is not None else None
            capture_times = trace['capture_times']
            capture_times_iter = (
                iter(capture_times) if capture_times is not None else None
            )

            coordinates_, segment_nums_ = get_coordinates(
                trace['segments'].geoms,  # type: ignore
                return_index=True,
            )
            coordinates: list[list[float]] = coordinates_.round(7).tolist()
            segment_nums: list[int] = segment_nums_.tolist()

            current_segment_num: int = -1
            trkseg: list[dict] = []
            trkpt: list[dict] = []

            for (lon, lat), segment_num in zip(coordinates, segment_nums, strict=True):
                # Handle start of new segment
                if segment_num > current_segment_num:
                    current_segment_num = segment_num
                    trkpt = []
                    trkseg.append({'trkpt': trkpt})

                data: dict[str, Any] = {'@lon': lon, '@lat': lat}
                if (
                    elevations_iter is not None
                    and (elevation := next(elevations_iter)) is not None
                ):
                    data['ele'] = round(elevation, 2)
                if (
                    capture_times_iter is not None
                    and (capture_time := next(capture_times_iter)) is not None
                ):
                    data['time'] = capture_time
                trkpt.append(data)

            # Add track if it is not empty
            if trkseg:
                trk.append(
                    {
                        'name': trace['name'],
                        'desc': trace['description'],
                        'url': f'/trace/{trace["id"]}',
                        'trkseg': trkseg,
                    }
                    if trace_is_timestamps_via_api(trace)
                    else {
                        'trkseg': trkseg,
                    }
                )

        return {'trk': trk}

    @staticmethod
    def decode_tracks(tracks: list[dict]) -> DecodeTracksResult:
        size: cython.size_t = 0
        segments: list[list[tuple[float, float]]] = []
        elevations: list[float | None] = []
        capture_times: list[datetime | None] = []
        has_elevation: cython.bint = False
        has_capture_times: cython.bint = False

        for track in tracks:
            for segment in track.get('trkseg', ()):
                points: list[tuple[float, float]] = []  # (lon, lat)

                for point in segment.get('trkpt', ()):
                    if (
                        (lon := point.get('@lon')) is None  #
                        or (lat := point.get('@lat')) is None
                    ):
                        continue

                    # Get elevation if available
                    elevation: float | None = point.get('ele')
                    if elevation is not None:
                        has_elevation = True

                    # Get timestamp if available
                    time: datetime | None = point.get('time')
                    if time is not None:
                        has_capture_times = True

                    # Add the point with elevation
                    points.append((lon, lat))
                    elevations.append(elevation)
                    capture_times.append(time)

                # Finish the segment if non-empty
                segment_size: cython.size_t = len(points)
                if segment_size:
                    if segment_size < 2:
                        raise_for.bad_trace_file(
                            'Trace segment is too short or incomplete'
                        )

                    size += segment_size
                    segments.append(points)

        if size < 2:
            raise_for.bad_trace_file('Trace is too short or incomplete')

        return DecodeTracksResult(
            size,
            MultiLineString(segments),
            elevations if has_elevation else None,
            capture_times if has_capture_times else None,
        )
