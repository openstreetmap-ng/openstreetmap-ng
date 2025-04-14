from datetime import datetime
from typing import Any, NamedTuple

import cython
from shapely import MultiLineString, force_2d, force_3d, get_coordinates

from app.lib.exceptions_context import raise_for
from app.models.db.trace import Trace, trace_is_timestamps_via_api


class DecodeTracksResult(NamedTuple):
    size: int
    segments: MultiLineString
    capture_times: list[datetime | None] | None


class FormatGPX:
    @staticmethod
    def encode_track(trace: Trace) -> dict:
        """
        >>> encode_track([
        ...     TraceSegment(...),
        ...     TraceSegment(...),
        ... ])
        {'trk': [{'trkseg': [{'trkpt': [{'@lon': 1, '@lat': 2}, {'@lon': 3, '@lat': 4}]}]}]}
        """
        capture_times = trace['capture_times']
        capture_times_iter = iter(capture_times) if capture_times is not None else None
        trkseg: list[dict] = []

        for segment in force_3d(trace['segments']).geoms:
            segment_coords: list[list[float]]
            segment_coords = get_coordinates(segment, include_z=True).tolist()  # type: ignore
            trkpt: list[dict] = []

            for lon, lat, elevation in segment_coords:
                data: dict[str, Any] = {'@lon': lon, '@lat': lat}
                if elevation:
                    data['ele'] = elevation
                if (
                    capture_times_iter is not None
                    and (capture_time := next(capture_times_iter)) is not None
                ):
                    data['time'] = capture_time
                trkpt.append(data)

            trkseg.append({'trkpt': trkpt})

        return {
            'trk': [
                (
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
            ]
        }

    @staticmethod
    def encode_tracks(traces: list[Trace]) -> dict:
        trk: list[dict] = []

        for trace in traces:
            coordinates_, segment_nums_ = get_coordinates(
                force_3d(trace['segments']).geoms,  # type: ignore
                include_z=True,
                return_index=True,
            )
            coordinates: list[list[float]] = coordinates_.tolist()
            segment_nums: list[int] = segment_nums_.tolist()
            capture_times = trace['capture_times']

            current_segment_num: int = -1
            trkseg: list[dict] = []
            trkpt: list[dict] = []

            for t in (
                zip(coordinates, segment_nums, capture_times, strict=True)
                if capture_times is not None
                else zip(coordinates, segment_nums, strict=True)
            ):
                (lon, lat, elevation) = t[0]
                segment_num = t[1]

                # Handle start of new segment
                if segment_num > current_segment_num:
                    current_segment_num = segment_num
                    trkpt = []
                    trkseg.append({'trkpt': trkpt})

                data: dict[str, Any] = {'@lon': lon, '@lat': lat}
                if elevation:
                    data['ele'] = elevation
                if capture_times is not None:
                    data['time'] = t[2]  # type: ignore
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
        size: cython.Py_ssize_t = 0
        segments: list[list[tuple[float, float, float]]] = []
        capture_times: list[datetime | None] = []
        has_elevation: cython.bint = False
        has_capture_times: cython.bint = False

        for track in tracks:
            for segment in track.get('trkseg', ()):
                points: list[tuple[float, float, float]] = []  # (lon, lat, elevation)

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
                    else:
                        elevation = 0

                    # Get timestamp if available
                    time: datetime | None = point.get('time')
                    if time is not None:
                        has_capture_times = True

                    # Add the point with elevation
                    points.append((lon, lat, elevation))
                    capture_times.append(time)

                # Finish the segment if non-empty
                segment_size: cython.Py_ssize_t = len(points)
                if segment_size:
                    if segment_size < 2:
                        raise_for.bad_trace_file(
                            'Trace segment is too short or incomplete'
                        )

                    size += segment_size
                    segments.append(points)

        if size < 2:
            raise_for.bad_trace_file('Trace is too short or incomplete')

        # Create the MultiLineString
        multilinestring = MultiLineString(segments)

        # Remove Z dimension if no elevation data
        if not has_elevation:
            multilinestring = force_2d(multilinestring)

        return DecodeTracksResult(
            size, multilinestring, capture_times if has_capture_times else None
        )
