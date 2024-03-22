import os
from pathlib import Path

import Cython.Compiler.Options as Options
from Cython.Build import cythonize
from setuptools import Extension, setup

Options.docstrings = False
Options.annotate = True


dirs = [
    # not supported by pydantic: 'app/controllers',
    'app/exceptions',
    'app/exceptions06',
    'app/format06',
    'app/format07',
    'app/lib',
    'app/middlewares',
    'app/repositories',
    'app/responses',
    'app/services',
    'app/validators',
]

paths = [p for d in dirs for p in Path(d).rglob('*.py')]


setup(
    ext_modules=cythonize(
        [
            Extension(
                path.with_suffix('').as_posix().replace('/', '.'),
                [str(path)],
                extra_compile_args=[
                    '-march=x86-64-v2',
                    '-mtune=generic',
                    '-ffast-math',
                    '-flto=auto',
                    '-fharden-compares',
                    '-fharden-conditional-branches',
                    # https://gcc.gnu.org/pipermail/gcc-patches/2023-August/628748.html
                    '-D_FORTIFY_SOURCE=3',
                    '-ftrivial-auto-var-init=zero',
                    # (incompatible) '-fPIE',
                    '-fstack-protector-strong',
                    '-fstack-clash-protection',
                    '-fcf-protection=full',
                    # https://developers.redhat.com/articles/2022/06/02/use-compiler-flags-stack-protection-gcc-and-clang#safestack_and_shadow_stack
                    '-mshstk',
                ],
                extra_link_args=[
                    '-flto=auto',
                    # https://gcc.gnu.org/pipermail/gcc-patches/2023-August/628748.html
                    # (incompatible) '-pie',
                    '-Wl,-z,relro,-z,now',
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
