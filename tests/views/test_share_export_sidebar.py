from pathlib import Path


def test_share_export_sidebar_does_not_offer_pdf_or_svg_but_keeps_raster_formats():
    template = Path("app/views/index/sidebar/share.html.jinja").read_text()

    assert '<option value="image/jpeg" data-suffix=".jpg">JPEG</option>' in template
    assert '<option value="image/png" data-suffix=".png">PNG</option>' in template
    assert '<option value="image/webp" data-suffix=".webp">WebP</option>' in template

    assert '<option value="image/svg+xml" data-suffix=".svg">SVG</option>' not in template
    assert '<option value="application/pdf" data-suffix=".pdf">PDF</option>' not in template
    assert "Canvas.toBlob(), which only supports raster image exports here." in template
