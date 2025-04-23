from pathlib import Path

from Cython.Build import cythonize
from Cython.Compiler import Options
from setuptools import Extension, setup

import app.config  # DO NOT REMOVE  # noqa: F401
from app.lib.pydantic_settings_integration import pydantic_settings_integration
from app.utils import calc_num_workers

CYTHON_MARCH = 'native'
CYTHON_MTUNE = 'native'
CYTHON_FLAGS = ''

pydantic_settings_integration(__name__, globals())

Options.docstrings = False
Options.annotate = True

dirs = (
    'app/exceptions',
    'app/exceptions06',
    'app/format',
    'app/lib',
    'app/middlewares',
    'app/responses',
    'app/services',
    'app/queries',
    'app/validators',
)

extra_paths = [
    Path(p)
    for p in (
        'app/db.py',
        'app/utils.py',
        'app/models/element.py',
        'app/models/scope.py',
        'app/models/tags_format.py',
        'scripts/preload_convert.py',
        'scripts/replication_download.py',
        'scripts/replication_generate.py',
    )
]

blacklist: dict[str, set[str]] = {
    'app/services/optimistic_diff': {
        # Reason: Unsupported PEP-654 Exception Groups
        # https://github.com/cython/cython/issues/4993
        '__init__.py',
    },
}

paths = [
    p
    for dir_ in dirs
    for p in (*Path(dir_).rglob('*.py'), *extra_paths)
    if p.name not in blacklist.get(p.parent.as_posix(), set())
]

extra_args: list[str] = [
    '-g',
    '-O3',
    '-flto=auto',
    '-pipe',
    # docs: https://gcc.gnu.org/onlinedocs/gcc-14.1.0/gcc.pdf
    f'-march={CYTHON_MARCH}',
    f'-mtune={CYTHON_MTUNE}',
    '-fhardened',
    '-funsafe-math-optimizations',
    '-fno-semantic-interposition',
    '-fno-plt',
    '-fvisibility=hidden',
    '-fipa-pta',
    # https://developers.redhat.com/articles/2022/06/02/use-compiler-flags-stack-protection-gcc-and-clang#safestack_and_shadow_stack
    '-mshstk',
    # https://stackoverflow.com/a/23501290
    '--param=max-vartrack-size=0',
    *CYTHON_FLAGS.split(),
]

setup(
    ext_modules=cythonize(
        [
            Extension(
                path.with_suffix('').as_posix().replace('/', '.'),
                [str(path)],
                extra_compile_args=extra_args,
                extra_link_args=extra_args,
                define_macros=[
                    ('CYTHON_PROFILE', '1'),
                ],
            )
            for path in paths
        ],
        nthreads=calc_num_workers(),
        compiler_directives={
            # https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html#compiler-directives
            'overflowcheck': True,
            'embedsignature': True,
            'profile': True,
            'language_level': 3,
        },
    ),
)
