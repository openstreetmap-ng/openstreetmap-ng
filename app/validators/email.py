import logging
from asyncio import Task, TaskGroup
from collections.abc import Iterable
from typing import Annotated, cast

from annotated_types import MaxLen, MinLen
from dns.asyncresolver import Resolver
from dns.exception import DNSException, Timeout
from dns.rdatatype import RdataType
from dns.rdtypes.mxbase import MXBase
from dns.resolver import NXDOMAIN, NoAnswer, NoNameservers
from email_validator import EmailNotValidError
from email_validator import validate_email as validate_email_
from email_validator.rfc_constants import EMAIL_MAX_LENGTH
from pydantic import AfterValidator

from app.config import TEST_ENV
from app.limits import EMAIL_DELIVERABILITY_CACHE_EXPIRE, EMAIL_DELIVERABILITY_DNS_TIMEOUT, EMAIL_MIN_LENGTH
from app.models.types import EmailType
from app.services.cache_service import CacheContext, CacheService

_cache_context = CacheContext('EmailValidator')
_resolver = Resolver()
_resolver.timeout = EMAIL_DELIVERABILITY_DNS_TIMEOUT.total_seconds()
_resolver.lifetime = _resolver.timeout + 2
_resolver.cache = None  # using valkey cache
_resolver.retry_servfail = True


def validate_email(email: str) -> EmailType:
    """
    Validate and normalize email address.

    Raises ValueError on error.

    >>> validate_email('example@ツ.ⓁⒾⒻⒺ')
    'example@ツ.life'
    """
    try:
        return EmailType(
            validate_email_(
                email,
                check_deliverability=False,
                test_environment=TEST_ENV,
            ).normalized
        )
    except EmailNotValidError as e:
        raise ValueError(f'Invalid email address {email!r}') from e


async def validate_email_deliverability(email: str) -> bool:
    """
    Validate deliverability of an email address.
    """
    try:
        info = validate_email_(
            email,
            check_deliverability=False,
            test_environment=TEST_ENV,
        )
    except EmailNotValidError:
        return False

    domain = info.ascii_domain

    async def factory() -> bytes:
        logging.debug('Email domain deliverability cache miss for %r', domain)
        success = await _check_domain_deliverability(domain)
        return b'\xff' if success else b'\x00'

    cache_entry = await CacheService.get(
        domain,
        context=_cache_context,
        factory=factory,
        ttl=EMAIL_DELIVERABILITY_CACHE_EXPIRE,
    )

    success = cache_entry.value == b'\xff'
    logging.info('Email domain deliverability for %r: %s', domain, success)
    return success


async def _check_domain_deliverability(domain: str) -> bool:
    success = False
    tasks: list[Task[None]] = []

    async with TaskGroup() as tg:

        async def task(rd: RdataType):
            nonlocal success

            try:
                answer = await _resolver.resolve(domain, rd)
                rrset = answer.rrset
            except NoAnswer:
                rrset = None
            except NXDOMAIN:
                return  # domain does not exist, skip further checks
            except (NoNameservers, Timeout):
                raise  # something's wrong on our side
            except DNSException:
                # some other error, log and proceed gracefully
                logging.warning('DNS error for %r (%r)', domain, rd)
                rrset = None

            if rd == RdataType.MX:
                if not rrset:
                    # on implicit mx, try a/aaaa
                    tasks.append(tg.create_task(task(RdataType.A)))
                    tasks.append(tg.create_task(task(RdataType.AAAA)))
                    return

                # mx - treat not-null answer as success
                # sort answers by preference in descending order
                rrset_by_preference = sorted(cast(Iterable[MXBase], rrset), key=lambda r: r.preference, reverse=True)
                exchange = str(rrset_by_preference[0].exchange)
                success = exchange != '.'
            elif rrset:
                # a/aaaa - treat any answer as success and cancel other tasks
                success = True
                for t in tasks:
                    t.cancel()

        tasks.append(tg.create_task(task(RdataType.MX)))

    return success


EmailValidator = AfterValidator(validate_email)
ValidatingEmailType = Annotated[EmailType, EmailValidator, MinLen(EMAIL_MIN_LENGTH), MaxLen(EMAIL_MAX_LENGTH)]

__all__ = ('ValidatingEmailType',)
