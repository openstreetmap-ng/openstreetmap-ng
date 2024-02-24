import logging

import cython

from app.config import TEST_ENV

if cython.compiled:
    logging.info('🐇 Cython modules are compiled')
elif not TEST_ENV:
    # require Cython modules to be compiled in production
    raise ImportError('Cython modules are not compiled')
else:
    logging.info('🐌 Cython modules are not compiled')
