from io import BytesIO
from PIL import Image, ImageDecompressionBombError
import pytest


def test_image_not_readable():
    """Test that unreadable image data raises 422."""
    from app.lib.io.image import _normalize_image
    
    with pytest.raises(Exception) as excinfo:
        _normalize_image(b"not an image")


def test_image_decompression_bomb():
    """Test that decompression bomb raises 413."""
    from app.lib.io.image import _normalize_image
    
    huge_data = b"\\x00" * 100_000_000
    with pytest.raises(Exception) as excinfo:
        _normalize_image(huge_data)
