from typing import override

from connectrpc.request import RequestContext

from app.controllers.web_note import build_note_data
from app.models.proto.note_connect import NoteService, NoteServiceASGIApplication
from app.models.proto.note_pb2 import GetNoteRequest, GetNoteResponse
from app.models.types import NoteId


class _Service(NoteService):
    @override
    async def get_note(
        self, request: GetNoteRequest, ctx: RequestContext
    ) -> GetNoteResponse:
        return GetNoteResponse(note=await build_note_data(NoteId(request.id)))


service = _Service()
asgi_app_cls = NoteServiceASGIApplication
