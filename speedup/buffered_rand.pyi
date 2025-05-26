from app.models.types import StorageKey

def buffered_randbytes(n: int, /) -> bytes:
    """Generate a secure random byte string of length n."""

def buffered_rand_urlsafe(n: int, /) -> str:
    """Generate a secure random URL-safe string of length n."""

def buffered_rand_storage_key(suffix: str = '', /) -> StorageKey:
    """Generate a secure random storage key."""
