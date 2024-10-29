from base64 import urlsafe_b64decode, urlsafe_b64encode

from google.protobuf.message import DecodeError

from app.lib.exceptions_context import raise_for
from app.models.proto.server_pb2 import UserTokenStruct


class UserTokenStructUtils:
    @staticmethod
    def from_str(s: str) -> UserTokenStruct:
        """
        Parse the given string into a user token struct.
        """
        try:
            return UserTokenStruct.FromString(urlsafe_b64decode(s))
        except DecodeError:
            raise_for().bad_user_token_struct()

    @staticmethod
    def to_str(u: UserTokenStruct) -> str:
        """
        Convert the given user token struct into a string.
        """
        return urlsafe_b64encode(u.SerializeToString()).decode()
