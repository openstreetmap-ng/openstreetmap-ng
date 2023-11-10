import functools
import logging
import time
from datetime import timedelta

from motor.core import AgnosticClientSession
from pymongo.errors import ConnectionFailure, OperationFailure

from db import MONGO_CLIENT

_DEFAULT_RETRY_TIMEOUT = 30


class Transaction:
    async def __aenter__(self) -> AgnosticClientSession:
        self.session = await MONGO_CLIENT.start_session()
        self.session.start_transaction()
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_val is None:
            # commit with retry
            # https://github.com/jdrumgoole/pymongo-transactions/blob/master/transaction_retry.py
            while True:
                try:
                    await self.session.commit_transaction()
                    break
                except (ConnectionFailure, OperationFailure) as e:
                    if e.has_error_label('UnknownTransactionCommitResult'):
                        logging.debug('UnknownTransactionCommitResult, retrying commit operation...')
                        continue
                    else:
                        raise e
        else:
            await self.session.abort_transaction()


def retry_transaction(timeout: timedelta | float = _DEFAULT_RETRY_TIMEOUT):
    if isinstance(timeout, timedelta):
        timeout_seconds = timeout.total_seconds()
    else:
        timeout_seconds = timeout

    def decorator(func):
        async def wrapper(*args, **kwargs):
            ts = time.perf_counter()

            while True:
                try:
                    return await func(*args, **kwargs)
                except (ConnectionFailure, OperationFailure) as e:
                    if e.has_error_label('TransientTransactionError') and time.perf_counter() - ts < timeout_seconds:
                        logging.debug('TransientTransactionError, retrying transaction...')
                        continue
                    else:
                        raise e

        return wrapper
    return decorator
