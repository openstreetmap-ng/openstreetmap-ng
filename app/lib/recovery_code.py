from blake3 import blake3
from pydantic import SecretBytes

# Crockford Base32 alphabet (no I, L, O, U to avoid ambiguity)
_ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'

# Normalization map for ambiguous characters (applied after uppercasing)
_NORMALIZATION_MAP = str.maketrans('OILU', '011V')

# Context string for BLAKE3 key derivation
_DERIVE_CONTEXT = 'openstreetmap-ng-totp-recovery-v1'


def encode_crockford_base32(value: int, length: int) -> str:
    """
    Encode an integer as Crockford Base32 string of specified length.

    Args:
        value: Integer to encode
        length: Desired string length

    Returns:
        Crockford Base32 encoded string
    """
    if value < 0:
        raise ValueError('Value must be non-negative')

    result = []
    for _ in range(length):
        result.append(_ALPHABET[value % 32])
        value //= 32

    return ''.join(reversed(result))


def decode_crockford_base32(code: str) -> int:
    """
    Decode a Crockford Base32 string to integer with normalization.

    Normalizes ambiguous characters:
    - O → 0
    - I/L → 1
    - U → V

    Args:
        code: Crockford Base32 string

    Returns:
        Decoded integer
    """
    # Remove hyphens and spaces, convert to uppercase
    code = code.replace('-', '').replace(' ', '').upper()

    # Normalize ambiguous characters
    code = code.translate(_NORMALIZATION_MAP)

    # Decode
    value = 0
    for char in code:
        if char not in _ALPHABET:
            raise ValueError(f'Invalid character in recovery code: {char}')
        value = value * 32 + _ALPHABET.index(char)

    return value


def generate_recovery_codes(secret: SecretBytes, base_index: int) -> list[str]:
    """
    Generate all 8 recovery codes for a given base index.

    Uses BLAKE3 key derivation with seek for efficient generation.
    Each code embeds a 3-bit offset (0-7) in the top bits and 47 bits
    of BLAKE3 output. Format: XXXXX-XXXXX (10 chars).

    Args:
        secret: Secret key for derivation
        base_index: Base index for this batch (0, 8, 16, 24, ...)

    Returns:
        List of 8 formatted recovery codes
    """
    # Derive key for this base using BLAKE3 KDF
    # Context includes base_index for domain separation
    context = f'{_DERIVE_CONTEXT}:{base_index}'
    hasher = blake3(secret.get_secret_value(), derive_key_context=context)

    codes = []
    for offset in range(8):
        # Seek to different position for each offset
        # Each code needs 6 bytes (48 bits, we'll use 47)
        seek_pos = offset * 6
        verification_bytes = hasher.digest(length=6, seek=seek_pos)
        verification_bits = int.from_bytes(verification_bytes, 'big') & ((1 << 47) - 1)

        # Embed 3-bit offset in top bits (bits 47-49)
        # Total: 50 bits = 10 chars of Base32
        code_bits = (offset << 47) | verification_bits

        # Encode as 10-character Crockford Base32
        code = encode_crockford_base32(code_bits, 10)

        # Format as XXXXX-XXXXX
        codes.append(f'{code[:5]}-{code[5:]}')

    return codes


def verify_recovery_code(secret: SecretBytes, base_index: int, code: str) -> int | None:
    """
    Verify a recovery code and return its offset if valid.

    Uses embedded 3-bit offset for O(1) verification with BLAKE3 seek.

    Args:
        secret: Secret key used for generation
        base_index: Current base index for this user
        code: Recovery code to verify

    Returns:
        Code offset (0-7) if valid, None otherwise
    """
    try:
        # Normalize and decode
        code_bits = decode_crockford_base32(code)

        # Extract embedded offset (top 3 bits)
        offset = code_bits >> 47
        verification_bits = code_bits & ((1 << 47) - 1)

        # Check if offset is in valid range (0-7)
        if offset >= 8:
            return None

        # Derive same key for this base
        context = f'{_DERIVE_CONTEXT}:{base_index}'
        hasher = blake3(secret.get_secret_value(), derive_key_context=context)

        # Seek to same position used during generation
        seek_pos = offset * 6
        expected_bytes = hasher.digest(length=6, seek=seek_pos)
        expected_verification = int.from_bytes(expected_bytes, 'big') & ((1 << 47) - 1)

        # Time-constant comparison
        if verification_bits != expected_verification:
            return None
        else:
            return offset
    except (ValueError, OverflowError):
        # Invalid format or decoding error
        return None
