import numpy as np

from app.lib.geo.mercator import mercator


def _assert_pole_endpoint(latitude):
    coords = np.array([[0.0, latitude], [0.0, latitude / 90 * 89]], dtype=np.float64)
    with np.errstate(all='raise'):
        result = mercator(coords, 100, 100)
    assert np.isfinite(result).all()
    np.testing.assert_allclose(result[:, 0], 50)
    np.testing.assert_allclose(sorted(result[:, 1]), [0, 100])


def test_mercator_south_pole_endpoint():
    _assert_pole_endpoint(-90.0)


def test_mercator_north_pole_endpoint():
    _assert_pole_endpoint(90.0)


def test_mercator_stationary_south_pole():
    coords = np.array([[0.0, -90.0], [0.0, -90.0]], dtype=np.float64)
    with np.errstate(all='raise'):
        result = mercator(coords, 100, 100)
    np.testing.assert_allclose(result, [[50, 50], [50, 50]])


def test_mercator_preserves_ordinary_projection():
    coords = np.array([[0.0, -80.0], [1.0, 0.0], [2.0, 80.0]], dtype=np.float64)
    latitudes = np.degrees(np.log(np.tan(np.radians(coords[:, 1]) / 2 + np.pi / 4)))
    expected_y = 100 - (latitudes - latitudes.min()) / np.ptp(latitudes) * 100
    result = mercator(coords, 100, 100)
    assert np.isfinite(result).all()
    np.testing.assert_allclose(result[:, 1], expected_y, atol=1e-12)
