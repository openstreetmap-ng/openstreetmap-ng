from typing import Any

from pydantic import AfterValidator


def Eq(expected: Any) -> AfterValidator:
    def _validate(v: Any) -> Any:
        if v != expected:
            raise ValueError(f'Expected {expected!r}, got {v!r}')
        return v
    return AfterValidator(_validate)


def Ne(expected: Any) -> AfterValidator:
    def _validate(v: Any) -> Any:
        if v == expected:
            raise ValueError(f'Expected not {expected!r}, got {v!r}')
        return v
    return AfterValidator(_validate)
