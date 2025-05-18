project(
  'xmltodict',
  'c',
  default_options: {
    'buildtype': 'release',
    'warning_level': '3',
    #'werror': 'true',
    'c_std': 'c23',
    'c_args': [
      '-march=native',
      '-mtune=native',
      #'-fhardened',
      '-funsafe-math-optimizations',
      '-fno-semantic-interposition',
      '-fno-plt',
      '-fvisibility=hidden',
      '-fipa-pta',
    ],
    #'b_lto': 'true',
    #'b_lundef': 'false',
    #'b_lto=true',
    #'b_lundef=false',
  },
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
  'lib',
  'lib.c',
  subdir: 'xmltodict',
  dependencies: [xml_dep],
  install: true,
)
