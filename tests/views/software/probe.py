"""Real router/template tests with only the auth/config-dependent page shell replaced."""

import importlib
import sys
import types
import unittest
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader
from starlette.responses import HTMLResponse
from starlette.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

translations = yaml.safe_load(
    (ROOT / 'config/locale/extra_en.yaml').read_text(encoding='utf-8')
)


def translate(key, **kwargs):
    value = translations
    for part in key.split('.'):
        value = value[part]
    return value.replace('{{', '{').replace('}}', '}').format(**kwargs)


env = Environment(
    loader=ChoiceLoader([
        DictLoader({
            '_base': '<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/bootstrap.css"><title>{% block title_prefix %}{% endblock %}</title></head><body>{% block body %}{% endblock %}</body></html>'
        }),
        FileSystemLoader(ROOT / 'app/views'),
    ]),
    autoescape=True,
)


async def render_response(name, data):
    return HTMLResponse(
        env.get_template(f'{name}.html.jinja').render(t=translate, **data)
    )


boundary = types.ModuleType('app.lib.render.response')
boundary.render_response = render_response
sys.modules[boundary.__name__] = boundary
router = importlib.import_module('app.controllers.software').router

app = FastAPI()
app.include_router(router)
app.mount('/static', StaticFiles(directory=ROOT / 'app/static'), name='static')
client = TestClient(app)


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.projects = []
        self.images = []
        self.selected = []
        self.forms = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'article':
            self.projects.append(values['data-software'])
        elif tag == 'img':
            self.images.append(values['src'])
        elif tag == 'option' and 'selected' in values:
            self.selected.append(values['value'])
        elif tag == 'form':
            self.forms.append((values['method'], values['action']))


class DirectoryTests(unittest.TestCase):
    def page(self, query=''):
        response = client.get('/software' + query)
        assert response.status_code == 200
        return Page(response.text), response.text

    def test_catalog_and_real_images(self):
        page, _ = self.page()
        assert page.projects == ['id', 'josm', 'organicmaps', 'qgis']
        assert page.forms == [('get', '/software')]
        for image in page.images:
            response = client.get(image)
            assert response.status_code == 200
            assert response.content.startswith(b'\x89PNG\r\n\x1a\n')

    def test_combined_filters_and_preserved_selection(self):
        page, _ = self.page(
            '?category=editing&platform=windows&license=open&maintenance=active'
        )
        assert page.projects == ['josm']
        assert page.selected == ['editing', 'windows', 'open', 'active']

    def test_each_filter_and_empty_combinations(self):
        for query, expected in (
            ('?platform=web', ['id']),
            ('?category=navigation', ['organicmaps']),
            ('?category=cartography&platform=linux', ['qgis']),
            ('?category=navigation&platform=linux', []),
            ('?license=proprietary', []),
            ('?maintenance=inactive', []),
        ):
            with self.subTest(query=query):
                page, text = self.page(query)
                assert page.projects == expected
                if not expected:
                    assert 'No projects match these filters.' in text

    def test_invalid_filters_rejected_as_validation_errors(self):
        for field in ('category', 'platform', 'license', 'maintenance'):
            assert (
                client.get('/software', params={field: '<script>'}).status_code == 422
            )

    def test_discovery_link_and_no_new_proto_requirement(self):
        navbar = (ROOT / 'app/views/navbar/navbar-right.tsx').read_text(
            encoding='utf-8'
        )
        assert 'href: "/software"' in navbar
        assert 'software_directory.title' in navbar


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/bootstrap.css':
            body = (
                ROOT / 'node_modules/bootstrap/dist/css/bootstrap.min.css'
            ).read_bytes()
            status, content_type = 200, 'text/css'
        else:
            response = client.get(self.path)
            body, status = response.content, response.status_code
            content_type = response.headers.get(
                'content-type', 'application/octet-stream'
            )
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    if '--serve' in sys.argv:
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        print(f'http://127.0.0.1:{server.server_port}', flush=True)
        server.serve_forever()
    else:
        unittest.main()
