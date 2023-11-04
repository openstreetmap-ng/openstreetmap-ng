from models.collections.acl import ACL
from models.str import NonEmptyStr


class ACLMX(ACL):
    mx: NonEmptyStr
