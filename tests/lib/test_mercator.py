import numpy as np

from app.lib.mercator import mercator


def test_mercator():
    coords = mercator(np.array([[0, 0], [0.8, 0.2], [1, 1]]), 100, 100).tolist()
    expected = np.array([[0, 100], [80, 80], [100, 0]])
    assert np.isclose(coords, expected, atol=1).all()


def test_mercator_zero():
    coords = mercator(np.array([[0, 0], [0, 0]]), 100, 100).tolist()
    expected = np.array([[50, 50], [50, 50]])
    assert np.isclose(coords, expected, atol=1).all()
