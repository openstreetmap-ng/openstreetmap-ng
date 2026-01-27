import {
  type DescMessage,
  type DescService,
  fromBinary,
  type MessageValidType,
} from "@bufbuild/protobuf"
import type { ConnectError } from "@connectrpc/connect"
import { createClient } from "@connectrpc/connect"
import { createConnectTransport } from "@connectrpc/connect-web"
import { StandardFeedbackDetailSchema } from "@lib/proto/shared_pb"
import { memoize } from "@std/cache/memoize"

export const fromBinaryValid = <Desc extends DescMessage>(
  schema: Desc,
  bytes: Uint8Array,
) => fromBinary(schema, bytes) as MessageValidType<Desc>

export const connectErrorToStandardFeedback = (err: ConnectError) => {
  const entries = err
    .findDetails(StandardFeedbackDetailSchema)
    .flatMap((d) => d.entries)
  return entries.length ? entries : null
}

export const connectErrorToMessage = (err: ConnectError) => {
  const feedback = connectErrorToStandardFeedback(err)
  return feedback ? feedback[0].message : err.rawMessage
}

const rpcTransport = createConnectTransport({
  baseUrl: "/rpc",
  useBinaryFormat: true,
  useHttpGet: true,
})

export const rpcClient = memoize(<T extends DescService>(service: T) =>
  createClient(service, rpcTransport),
)
