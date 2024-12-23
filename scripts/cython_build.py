import os
from collections.abc import Iterable
from itertools import chain
from pathlib import Path

from Cython.Build import cythonize
from Cython.Compiler import Options
from setuptools import Extension, setup

import app.config  # DO NOT REMOVE  # noqa: F401

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

extra_paths: Iterable[Path] = map(
    Path,
    (
        'app/db.py',
        'app/utils.py',
        'app/models/element.py',
        'app/models/scope.py',
        'app/models/tags_format.py',
        'scripts/preload_convert.py',
        'scripts/replication.py',
    ),
)

blacklist: dict[str, set[str]] = {
    'app/services': {
        'email_service.py',
    },
    'app/services/optimistic_diff': {
        '__init__.py',
    },
}

paths = (
    p
    for dir_ in dirs  #
    for p in chain(Path(dir_).rglob('*.py'), extra_paths)
    if p.name not in blacklist.get(p.parent.as_posix(), set())
)

extra_args: list[str] = [
    '-g',
    '-O3',
    '-flto=auto',
    '-pipe',
    # docs: https://gcc.gnu.org/onlinedocs/gcc-14.1.0/gcc.pdf
    '-march=' + os.getenv('CYTHON_MARCH', 'native'),
    '-mtune=' + os.getenv('CYTHON_MTUNE', 'native'),
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
    *os.getenv('CYTHON_FLAGS', '').split(),
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
        nthreads=os.process_cpu_count(),  # pyright: ignore[reportArgumentType]
        compiler_directives={
            # https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html#compiler-directives
            'overflowcheck': True,
            'profile': True,
            'language_level': 3,
        },
    ),
)
