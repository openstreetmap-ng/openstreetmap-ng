from pathlib import Path


def test_share_export_sidebar_offers_only_raster_download_formats():
    source = Path("app/views/index/sidebar/share.tsx").read_text()

    assert '{ mimeType: "image/jpeg", suffix: ".jpg", label: "JPEG" }' in source
    assert '{ mimeType: "image/png", suffix: ".png", label: "PNG" }' in source
    assert '{ mimeType: "image/webp", suffix: ".webp", label: "WebP" }' in source

    assert "image/svg+xml" not in source
    assert "application/pdf" not in source


def test_share_export_sidebar_falls_back_from_stale_unsupported_format():
    source = Path("app/views/index/sidebar/share.tsx").read_text()

    assert "const DEFAULT_SHARE_FORMAT = SHARE_FORMATS[0]" in source
    assert "?? DEFAULT_SHARE_FORMAT" in source
    assert "getShareFormat(shareExportFormatStorage.value).mimeType" in source


def test_share_export_documents_future_svg_pdf_renderer():
    source = Path("app/views/map/export-image.ts").read_text()

    assert "Canvas.toBlob() exports raster images from the map canvas" in source
    assert "https://render.openstreetmap.org/" in source
