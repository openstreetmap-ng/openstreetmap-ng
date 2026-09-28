from app.middlewares.headers_middleware import CSP_HEADER


def _csp_directive_values(name: str) -> set[str]:
    for directive in CSP_HEADER.split('; '):
        directive_name, *values = directive.split()
        if directive_name == name:
            return set(values)
    raise AssertionError(f'Missing CSP directive: {name}')


def test_csp_frame_src_allows_achavi_embed():
    assert 'https://overpass-api.de' in _csp_directive_values('frame-src')
