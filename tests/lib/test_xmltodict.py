from datetime import datetime

import pytest
import xmltodict

from cython_pkg.xmltodict import XMLToDict


@pytest.mark.parametrize('input', [
    ('<?xml version="1.0" encoding="UTF-8"?><osmChange><modify><node id="1" visible="true" version="2" changeset="42" timestamp="2023-10-25T22:47:09Z" user="test" uid="42" lat="0.0" lon="0.0"><tag k="test" v="zebra"/></node></modify><create><node id="2" visible="true" version="1" changeset="42" timestamp="2023-10-25T22:47:09Z" user="test" uid="42" lat="0.0" lon="0.0"><tag k="test" v="zebra"/></node></create><modify><node id="11289669127" visible="true" version="2" changeset="42" timestamp="2023-10-25T22:47:09Z" user="test" uid="42" lat="0.0" lon="0.0"><tag k="test1" v="test1"/><tag k="test2" v="test2"/></node></modify></osmChange>'),
    ('<root><key1 attr="1"/><key2>text</key2><key1 attr="2"/></root>'),
    ('<root><key1 attr="1"/><key2>text</key2><key2 attr="2">text2</key2></root>')
])
def test_parse(input):
    output = XMLToDict.parse(input)
    expected = xmltodict.parse(input, force_list=XMLToDict.force_list, postprocessor=XMLToDict.postprocessor)
    assert output == expected


@pytest.mark.parametrize('input,output', [
    ('<osmChange><modify id="1"/><create id="2"><tag k="test" v="zebra"/></create><modify id="3"/></osmChange>',
     {'osmChange': [
         ('modify', {'@id': 1}),
         ('create', {'@id': 2, 'tag': [{'@k': 'test', '@v': 'zebra'}]}),
         ('modify', {'@id': 3}),
     ]}),
])
def test_parse_sequence(input, output):
    assert XMLToDict.parse(input, sequence=True) == output


@pytest.mark.parametrize('input,output', [
    (
        {'osmChange': [
            ('@attrib', 'yes'),
            ('modify', '1'),
            ('create', '2'),
            ('modify', '3'),
            ('modify', {
                '@id': '4',
                '@timestamp': datetime(2020, 1, 1),
                '@visible': True,
            })
        ]},
        '<?xml version=\'1.0\' encoding=\'UTF-8\'?>\n<osmChange attrib="yes"><modify>1</modify><create>2</create><modify>3</modify><modify id="4" timestamp="2020-01-01T00:00:00Z" visible="true" /></osmChange>'
    ),
    (
        {'osmChange': {
            'create': [],
            'modify': [{
                '@id': 1,
            }, {
                '@id': 2,
                'tag': [{
                        '@k': 'test',
                        '@v': 'zebra',
                        }, {
                        '@k': 'test2',
                        '@v': 'zebra2',
                        }]
            }, {}],
            'delete': {
                '@id': 3,
            },
        }},
        '<?xml version=\'1.0\' encoding=\'UTF-8\'?>\n<osmChange><modify id="1" /><modify id="2"><tag k="test" v="zebra" /><tag k="test2" v="zebra2" /></modify><modify /><delete id="3" /></osmChange>'
    )
])
def test_unparse(input, output):
    assert XMLToDict.unparse(input) == output


@pytest.mark.xfail
def test_unparse_multi_root():
    XMLToDict.unparse({'root1': {}, 'root2': {}})


@pytest.mark.xfail
def test_unparse_emtpy():
    XMLToDict.unparse({})
