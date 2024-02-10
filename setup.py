import os
from pathlib import Path

import Cython.Compiler.Options as Options
from Cython.Build import cythonize
from setuptools import Extension, setup

Options.docstrings = False
Options.annotate = True


dirs = [
    'app/controllers',
    'app/exceptions',
    'app/exceptions06',
    'app/format06',
    'app/format07',
    'app/lib',
    'app/middlewares',
    'app/responses',
    'app/validators',
]

paths = [p for d in dirs for p in Path(d).rglob('*.py')]


setup(
    ext_modules=cythonize(
        [
            Extension(
                str(path.with_suffix('')).replace('/', '.'),
                [str(path)],
                extra_compile_args=[
                    '-march=x86-64-v2',
                    '-mtune=generic',
                    '-ffast-math',
                    '-fopenmp',
                    '-flto=auto',
                ],
                extra_link_args=[
                    '-fopenmp',
                    '-flto=auto',
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
