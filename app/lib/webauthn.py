from hashlib import sha256
from typing import Literal, NamedTuple, NotRequired, TypedDict
from urllib.parse import urlsplit

import cbor2
import cython
import orjson
from Crypto.Hash import SHA256
from Crypto.PublicKey import ECC
from Crypto.Signature import DSS, eddsa
from starlette import status
from starlette.exceptions import HTTPException

from app.config import APP_URL
from app.models.db.user_passkey import UserPasskey
from app.models.proto.shared_pb2 import PasskeyAssertion

_ClientDataType = Literal['webauthn.create', 'webauthn.get']


class _ClientData(TypedDict):
    challenge: str  # base64url encoded version of the cryptographic challenge
    origin: str
    type: _ClientDataType
    crossOrigin: NotRequired[bool]
    topOrigin: NotRequired[str]


class _AuthData(NamedTuple):
    credential_id: bytes
    algorithm: int
    public_key: bytes


# https://developer.mozilla.org/en-US/docs/Web/API/Web_Authentication_API/Authenticator_data
_AUTH_DATA_RP_ID_HASH_LEN = 32
_AUTH_DATA_FLAGS_OFFSET = 32
_AUTH_DATA_SIGN_COUNT_OFFSET = 33
_AUTH_DATA_CRED_ID_LEN_OFFSET = 53
_AUTH_DATA_CRED_ID_OFFSET = 55

_FLAG_UP = 1 << 0  # User Present
_FLAG_UV = 1 << 2  # User Verified
_FLAG_AT = 1 << 6  # Attested credential data

_RP_ID_HASH = sha256(urlsplit(APP_URL).hostname.encode()).digest()  # type: ignore

_COSE_KTY = 1
_COSE_ALG = 3
_COSE_CRV = -1
_COSE_X = -2
_COSE_Y = -3

_COSE_KTY_OKP = 1
_COSE_KTY_EC2 = 2
_COSE_ALG_ES256 = -7
_COSE_ALG_EDDSA = -8
_COSE_CRV_P256 = 1
_COSE_CRV_ED25519 = 6

_ED25519_DER_PREFIX = b'\x30\x2a\x30\x05\x06\x03\x2b\x65\x70\x03\x21\x00'


def parse_client_data(
    client_data_json: bytes, *, expected_type: _ClientDataType
) -> _ClientData:
    """Parse and validate client data JSON."""
    data: _ClientData = orjson.loads(client_data_json)

    type = data['type']
    if type != expected_type:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f'ClientData: Invalid type: {type}'
        )

    origin = data['origin']
    if origin != APP_URL:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f'ClientData: Invalid origin: {origin}'
        )

    if data.get('crossOrigin'):
        top_origin = data.get('topOrigin')
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f'ClientData: Invalid topOrigin: {top_origin}'
        )

    return data


def parse_auth_data(auth_data: bytes, *, require_uv: bool = True) -> _AuthData | None:
    """Parse and validate authenticator data."""
    if auth_data[:_AUTH_DATA_RP_ID_HASH_LEN] != _RP_ID_HASH:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'AuthData: Invalid RP ID')

    flags = auth_data[_AUTH_DATA_FLAGS_OFFSET]
    if not (flags & _FLAG_UP):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'AuthData: User not present')
    if require_uv and not (flags & _FLAG_UV):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, 'AuthData: User verification required'
        )
    if not (flags & _FLAG_AT):
        return None

    cred_id_len = int.from_bytes(
        auth_data[_AUTH_DATA_CRED_ID_LEN_OFFSET:_AUTH_DATA_CRED_ID_OFFSET]
    )
    assert cred_id_len <= 1023
    credential_id = auth_data[
        _AUTH_DATA_CRED_ID_OFFSET : _AUTH_DATA_CRED_ID_OFFSET + cred_id_len
    ]
    cose_key = auth_data[_AUTH_DATA_CRED_ID_OFFSET + cred_id_len :]
    algorithm, public_key = _parse_cose_public_key(cose_key)

    return _AuthData(
        credential_id=credential_id,
        algorithm=algorithm,
        public_key=public_key,
    )


def verify_assertion(
    passkey: UserPasskey,
    assertion: PasskeyAssertion,
) -> int:
    """Verify assertion signature. Returns updated sign count."""
    client_data_json = assertion.client_data_json
    authenticator_data = assertion.authenticator_data

    stored_sign_count = passkey['sign_count']
    new_sign_count = int.from_bytes(
        authenticator_data[
            _AUTH_DATA_SIGN_COUNT_OFFSET : _AUTH_DATA_SIGN_COUNT_OFFSET + 4
        ]
    )
    if (stored_sign_count or new_sign_count) and new_sign_count <= stored_sign_count:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f'Assertion: Invalid sign count ({new_sign_count} <= {stored_sign_count})',
        )

    if not _verify_signature(
        passkey,
        data=authenticator_data + sha256(client_data_json).digest(),
        signature=assertion.signature,
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Assertion: Bad signature')

    return new_sign_count


@cython.cfunc
def _parse_cose_public_key(cose_key: bytes) -> tuple[int, bytes]:
    """Parse a COSE public key and return (algorithm, raw_key_bytes)."""
    key_map = cbor2.loads(cose_key)
    kty = key_map.get(_COSE_KTY)
    alg = key_map.get(_COSE_ALG)
    crv = key_map.get(_COSE_CRV)
    x = key_map.get(_COSE_X)
    y = key_map.get(_COSE_Y)

    if kty == _COSE_KTY_OKP and alg == _COSE_ALG_EDDSA:
        if crv == _COSE_CRV_ED25519:
            assert isinstance(x, bytes) and len(x) == 32, 'Invalid Ed25519 public key'
            return (_COSE_ALG_EDDSA, x)
        raise NotImplementedError(f'Unsupported EdDSA curve {crv!r}')

    if kty == _COSE_KTY_EC2 and alg == _COSE_ALG_ES256:
        if crv == _COSE_CRV_P256:
            assert isinstance(x, bytes) and len(x) == 32, 'Invalid P-256 x coordinate'
            assert isinstance(y, bytes) and len(y) == 32, 'Invalid P-256 y coordinate'
            return (_COSE_ALG_ES256, x + y)
        raise NotImplementedError(f'Unsupported ES256 curve {crv!r}')

    raise NotImplementedError(f'Unsupported algorithm kty={kty!r} alg={alg!r}')


@cython.cfunc
def _verify_signature(
    passkey: UserPasskey,
    *,
    data: bytes,
    signature: bytes,
) -> bool:
    """Verify a cryptographic signature using the specified COSE algorithm."""
    algorithm = passkey['algorithm']
    public_key = passkey['public_key']

    if algorithm == _COSE_ALG_EDDSA:
        der = _ED25519_DER_PREFIX + public_key
        key = ECC.import_key(der)
        verifier = eddsa.new(key, 'rfc8032')
        try:
            verifier.verify(data, signature)
        except ValueError:
            return False
        return True

    if algorithm == _COSE_ALG_ES256:
        x = int.from_bytes(public_key[:32])
        y = int.from_bytes(public_key[32:])
        key = ECC.construct(curve='P-256', point_x=x, point_y=y)
        verifier = DSS.new(key, 'fips-186-3', 'der')
        msg_hash = SHA256.new(data)
        try:
            verifier.verify(msg_hash, signature)
        except ValueError:
            return False
        return True

    raise NotImplementedError(f'Unsupported algorithm {algorithm!r}')
