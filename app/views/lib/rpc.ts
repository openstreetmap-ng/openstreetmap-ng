import type { DescService } from "@bufbuild/protobuf"
import type { ConnectError } from "@connectrpc/connect"
import { createClient } from "@connectrpc/connect"
import { createConnectTransport } from "@connectrpc/connect-web"
import {
  StandardFeedbackDetail_Severity,
  StandardFeedbackDetailSchema,
} from "@lib/proto/shared_pb"
import type { APIDetail } from "@lib/standard-form"
import { memoize } from "@std/cache/memoize"

const connectErrorToStandardFeedback = (err: ConnectError) => {
  const details = err.findDetails(StandardFeedbackDetailSchema)
  if (!details.length) return null

  const out: APIDetail[] = []
  for (const d of details) {
    for (const entry of d.entries) {
      out.push({
        type: StandardFeedbackDetail_Severity[
          entry.severity
        ] as keyof typeof StandardFeedbackDetail_Severity,
        loc: [null, entry.field ?? null],
        msg: entry.message,
      })
    }
  }

  return out.length ? out : null
}

export const connectErrorToMessage = (err: ConnectError) => {
  const feedback = connectErrorToStandardFeedback(err)
  return !feedback?.length ? err.rawMessage : feedback[0].msg
}

const rpcTransport = createConnectTransport({
  baseUrl: "/rpc",
  useBinaryFormat: true,
  useHttpGet: true,
})

export const rpcClient = memoize(<T extends DescService>(service: T) =>
  createClient(service, rpcTransport),
)
