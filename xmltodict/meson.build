project(
  'xmltodict',
  'c',
  default_options: {
    'buildtype': 'release',
    'warning_level': '3',
    'c_std': 'c23',
  },
  meson_version: '>=1.2.0',
)

xml_dep = subproject(
  'libxml2',
  default_options: {
    'minimum': 'true',
    'output': 'enabled',
    'reader': 'enabled',
    'threads': 'enabled',
    'writer': 'enabled',
  },
).get_variable('xml_dep')

py = import('python').find_installation(pure: false)
py.extension_module(
  'parse',
  'parse.c',
  subdir: 'xmltodict',
  dependencies: [xml_dep],
  install: true,
)
