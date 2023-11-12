from glob import glob

import Cython.Compiler.Options as options
from Cython.Build import cythonize
from setuptools import Extension, setup

options.docstrings = True
options.embed_pos_in_docstring = True
options.annotate = True

setup(
    ext_modules = cythonize([
        Extension(
            '*', glob('cython_pkg/*.py*'),
            extra_compile_args=[
                '-march=native',
                '-ffast-math',
            ],
        )
    ], compiler_directives={
        # https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html#compiler-directives
        'language_level': 3,
        'embedsignature': True,
    }),
)
