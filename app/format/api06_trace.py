import cython

from app.models.db.trace import Trace, TraceMetaInitValidator


class Trace06Mixin:
    @staticmethod
    def encode_gpx_file(trace: Trace):
        """
        >>> encode_gpx_file(Trace(...))
        {'gpx_file': {'@id': 1, '@uid': 1234, ...}}
        """
        return {'gpx_file': _encode_gpx_file(trace)}

    @staticmethod
    def encode_gpx_files(traces: list[Trace]):
        """
        >>> encode_gpx_files([
        ...     Trace(...),
        ...     Trace(...),
        ... ])
        {'gpx_file': [{'@id': 1, '@uid': 1234, ...}, {'@id': 2, '@uid': 1234, ...}]}
        """
        return {'gpx_file': list(map(_encode_gpx_file, traces))}

    @staticmethod
    def decode_gpx_file(gpx_file: dict):
        """Decode trace metadata from gpx_file structure."""
        return TraceMetaInitValidator.validate_python({
            'name': gpx_file.get('@name'),
            'description': gpx_file.get('description'),
            'tags': gpx_file.get('tag', []),
            'visibility': gpx_file.get('@visibility'),
        })


@cython.cfunc
def _encode_gpx_file(trace: Trace):
    """
    >>> _encode_gpx_file(Trace(...))
    {'@id': 1, '@uid': 1234, ...}
    """
    x, y = trace['coords'][0].tolist()  # pyright: ignore [reportTypedDictNotRequiredAccess]
    return {
        '@id': trace['id'],
        '@uid': trace['user_id'],
        '@user': trace['user']['display_name'],  # pyright: ignore [reportTypedDictNotRequiredAccess]
        '@timestamp': trace['created_at'],
        '@name': trace['name'],
        '@lon': x,
        '@lat': y,
        '@visibility': trace['visibility'],
        '@pending': False,
        'description': trace['description'],
        'tag': trace['tags'],
    }
