from pathlib import Path


def test_share_export_sidebar_only_offers_raster_formats():
    share_sidebar = Path("app/views/index/sidebar/share.tsx").read_text()
    export_image = Path("app/views/map/export-image.ts").read_text()

    assert 'mimeType: "image/jpeg"' in share_sidebar
    assert 'mimeType: "image/png"' in share_sidebar
    assert 'mimeType: "image/webp"' in share_sidebar

    assert 'mimeType: "image/svg+xml"' not in share_sidebar
    assert 'mimeType: "application/pdf"' not in share_sidebar
    assert "Re-enable SVG/PDF" in share_sidebar
    assert "render.openstreetmap.org" in share_sidebar
    assert "Canvas.toBlob() only supports raster image exports" in export_image
