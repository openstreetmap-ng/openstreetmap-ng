import logging

import cython

from app.config import TEST_ENV

if cython.compiled:
    logging.info('🐇 Cython is compiled')
elif not TEST_ENV:
    # require Cython modules to be compiled in production
    raise ImportError('Cython modules are not compiled')
else:
    logging.info('🐌 Cython is not compiled')
