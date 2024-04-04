import pytest
from anyio import Path

from app.format06 import Format06
from app.lib.trace_image import TraceImage
from app.lib.xmltodict import XMLToDict

pytestmark = pytest.mark.anyio


async def test_generate():
    # TODO: fixture?
    gpx = await Path('tests/data/11152535.gpx').read_bytes()
    data = XMLToDict.parse(gpx)
    trace_points = Format06.decode_tracks(data['gpx']['trk'])
    animation, icon = TraceImage.generate(trace_points)

    assert isinstance(animation, bytes)
    assert isinstance(icon, bytes)
    assert len(icon) < len(animation)
