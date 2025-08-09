from typing import Annotated, NewType

from annotated_types import Interval
from pydantic import SecretStr

Email = NewType('Email', str)
DisplayName = NewType('DisplayName', str)

ClientId = NewType('ClientId', str)
LocaleCode = NewType('LocaleCode', str)
Password = NewType('Password', SecretStr)
StorageKey = NewType('StorageKey', str)

Longitude = Annotated[float, Interval(ge=-180, le=180)]
Latitude = Annotated[float, Interval(ge=-90, le=90)]
Zoom = Annotated[int, Interval(ge=0, le=25)]

ApplicationId = NewType('ApplicationId', int)
ChangesetCommentId = NewType('ChangesetCommentId', int)
ChangesetId = NewType('ChangesetId', int)
DiaryCommentId = NewType('DiaryCommentId', int)
DiaryId = NewType('DiaryId', int)
MailId = NewType('MailId', int)
MessageId = NewType('MessageId', int)
NoteCommentId = NewType('NoteCommentId', int)
NoteId = NewType('NoteId', int)
OAuth2TokenId = NewType('OAuth2TokenId', int)
ReportCommentId = NewType('ReportCommentId', int)
ReportId = NewType('ReportId', int)
SequenceId = NewType('SequenceId', int)
TraceId = NewType('TraceId', int)
UserId = NewType('UserId', int)
UserPrefKey = NewType('UserPrefKey', str)
UserPrefVal = NewType('UserPrefVal', str)
UserSubscriptionTargetId = ChangesetId | DiaryId | NoteId | UserId
UserTokenId = NewType('UserTokenId', int)
