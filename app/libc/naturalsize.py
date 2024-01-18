import cython

_suffixes = (' KiB', ' MiB', ' GiB', ' TiB', ' PiB', ' EiB', ' ZiB', ' YiB')


def naturalsize(value: float | str) -> str:
    """ """
    base: cython.int = 1024
    bytes_: cython.double = float(value)

    if bytes_ < base:
        return f'{bytes_:.0f} B'

    for s in _suffixes:
        bytes_ /= base

        if bytes_ < base:
            return f'{bytes_:.1f}{s}'

    return '(too large to display)'
