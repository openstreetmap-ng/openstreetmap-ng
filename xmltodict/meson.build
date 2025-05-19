project(
  'xmltodict',
  'c',
  default_options: {
    'c_std': 'c23',
  },
  meson_version: '>=1.2.0',
)

py = import('python').find_installation(pure: false)
py.extension_module(
  'parse',
  'parse.c',
  subdir: 'xmltodict',
  dependencies: [dependency('libxml-2.0')],
  install: true,
)
