import cython

from app.config import TEST_ENV

if cython.compiled:
    print('🐇 Cython is compiled')
elif not TEST_ENV:
    # require Cython modules to be compiled in production
    raise ImportError('Cython modules are not compiled')
else:
    print('🐌 Cython is not compiled')
