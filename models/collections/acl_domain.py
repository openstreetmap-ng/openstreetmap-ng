from models.collections.acl import ACL
from models.str import NonEmptyStr


class ACLDomain(ACL):
    domain: NonEmptyStr
