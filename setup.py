from os import cpu_count

import Cython.Compiler.Options as Options
from Cython.Build import cythonize
from setuptools import Extension, setup

Options.docstrings = False
Options.annotate = True


setup(
    ext_modules=cythonize(
        [
            Extension(
                '*',
                ['app/libc/*.py'],
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
        ],
        nthreads=cpu_count(),
        compiler_directives={
            # https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html#compiler-directives
            'overflowcheck': True,
            'language_level': 3,
        },
    ),
)
