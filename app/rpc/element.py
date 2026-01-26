from typing import override

from connectrpc.request import RequestContext

from app.controllers.web_element import build_element_data
from app.lib.exceptions_context import raise_for
from app.models.element import ElementId
from app.models.proto.element_connect import (
    ElementService,
    ElementServiceASGIApplication,
)
from app.models.proto.element_pb2 import (
    GetElementRequest,
    GetElementResponse,
)
from app.models.proto.shared_pb2 import ElementType as ProtoElementType
from app.models.proto.shared_pb2 import ElementVersionRef
from app.queries.element_query import ElementQuery
from speedup import typed_element_id


class _Service(ElementService):
    @override
    async def get_element(
        self, request: GetElementRequest, ctx: RequestContext
    ) -> GetElementResponse:
        ref_kind = request.WhichOneof('ref')
        ref: ElementVersionRef = getattr(request, ref_kind)
        tid = typed_element_id(ProtoElementType.Name(ref.type), ElementId(ref.id))

        at_sequence_id = await ElementQuery.get_current_sequence_id()

        if ref_kind == 'version':
            versioned_tid = (tid, ref.version)
            elements = await ElementQuery.find_by_versioned_refs(
                [versioned_tid], at_sequence_id=at_sequence_id, limit=1
            )
        else:
            elements = await ElementQuery.find_by_refs(
                [tid], at_sequence_id=at_sequence_id, limit=1
            )

        element = next(iter(elements), None)
        if element is None:
            raise_for.element_not_found(tid)

        return GetElementResponse(
            element=await build_element_data(
                element,
                at_sequence_id,
                include_parents_entries=ref_kind == 'element' or element['latest'],
            )
        )


service = _Service()
asgi_app_cls = ElementServiceASGIApplication
