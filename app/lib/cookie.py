from datetime import timedelta
from http.cookies import SimpleCookie
from typing import Literal

import cython
from connectrpc.request import RequestContext
from pydantic import SecretStr
from starlette.responses import Response

from app.config import ENV

type CookieTarget = Response | RequestContext
type CookieSameSite = Literal['lax', 'strict', 'none']


@cython.cfunc
def _max_age_seconds(max_age: timedelta | int | None):
    if max_age is None:
        return None
    if isinstance(max_age, timedelta):
        return int(max_age.total_seconds())
    return max_age


@cython.cfunc
def _cookie_value(value: str | SecretStr):
    return value.get_secret_value() if isinstance(value, SecretStr) else value


def set_cookie(
    target: CookieTarget,
    key: str,
    value: str | SecretStr,
    *,
    max_age: timedelta | int | None = None,
    path: str = '/',
    secure: bool = ENV != 'dev',
    httponly: bool = True,
    samesite: CookieSameSite = 'lax',
):
    value = _cookie_value(value)
    max_age = _max_age_seconds(max_age)

    if isinstance(target, Response):
        target.set_cookie(
            key=key,
            value=value,
            max_age=max_age,
            path=path,
            secure=secure,
            httponly=httponly,
            samesite=samesite,
        )
        return

    cookie = SimpleCookie()
    cookie[key] = value
    cookie[key]['path'] = path
    cookie[key]['secure'] = secure
    cookie[key]['httponly'] = httponly
    cookie[key]['samesite'] = samesite
    if max_age is not None:
        cookie[key]['max-age'] = max_age
    target.response_headers().add('set-cookie', cookie.output(header='').lstrip())


def delete_cookie(
    target: CookieTarget,
    key: str,
    *,
    path: str = '/',
    secure: bool = ENV != 'dev',
    httponly: bool = True,
    samesite: CookieSameSite = 'lax',
):
    if isinstance(target, Response):
        target.delete_cookie(
            key,
            path=path,
            secure=secure,
            httponly=httponly,
            samesite=samesite,
        )
        return

    cookie = SimpleCookie()
    cookie[key] = ''
    cookie[key]['path'] = path
    cookie[key]['max-age'] = 0
    cookie[key]['expires'] = 'Thu, 01 Jan 1970 00:00:00 GMT'
    cookie[key]['secure'] = secure
    cookie[key]['httponly'] = httponly
    cookie[key]['samesite'] = samesite
    target.response_headers().add('set-cookie', cookie.output(header='').lstrip())


def set_auth_cookie(
    target: CookieTarget,
    token: SecretStr,
    *,
    max_age: timedelta | int | None = None,
):
    set_cookie(target, 'auth', token, max_age=max_age)


def delete_auth_cookie(target: CookieTarget):
    delete_cookie(target, 'auth')
