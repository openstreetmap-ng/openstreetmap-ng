import os
from pathlib import Path

import Cython.Compiler.Options as Options
from Cython.Build import cythonize
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

blacklist: dict[str, set[str]] = {
    'app/services': {
        'email_service.py',
    }
}

paths = []
for dir in dirs:
    dir_blacklist = blacklist.get(dir, set())
    for p in Path(dir).rglob('*.py'):
        if p.name not in dir_blacklist:
            paths.append(p)  # noqa: PERF401

setup(
    ext_modules=cythonize(
        [
            Extension(
                path.with_suffix('').as_posix().replace('/', '.'),
                [str(path)],
                extra_compile_args=[
                    # docs: https://gcc.gnu.org/onlinedocs/gcc-14.1.0/gcc.pdf
                    '-march=x86-64-v3',
                    '-mtune=generic',
                    '-ffast-math',
                    '-fharden-compares',
                    '-fharden-conditional-branches',
                    '-fharden-control-flow-redundancy',
                    '-fhardened',
                    # https://developers.redhat.com/articles/2022/06/02/use-compiler-flags-stack-protection-gcc-and-clang#safestack_and_shadow_stack
                    '-mshstk',
                ],
            )
            for path in paths
        ],
        nthreads=os.cpu_count(),
        compiler_directives={
            # https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html#compiler-directives
            'overflowcheck': True,
            'language_level': 3,
        },
    ),
)
