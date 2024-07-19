import cython


def naturalsize(value: float) -> str:
    """
    Format a number of byteslike a human readable filesize (eg. 10 KiB, 2.3 MiB, 1.2 GiB, etc).

    >>> naturalsize(10000)
    '9.77 KiB'
    """
    base: cython.int = 1024
    bytes_: cython.double = float(value)

    if bytes_ < base:
        return f'{bytes_:.0f} B'

    for s in (' KiB', ' MiB', ' GiB', ' TiB', ' PiB', ' EiB', ' ZiB', ' YiB'):
        bytes_ /= base
        if bytes_ < base:
            return f'{bytes_:.2f}{s}' if bytes_ < 10 else f'{bytes_:.1f}{s}'

    return '(too large to display)'
