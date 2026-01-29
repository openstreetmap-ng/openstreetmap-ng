import {
  type DescMessage,
  type DescMethodUnary,
  type DescService,
  fromBinary,
  type MessageInitShape,
  type MessageValidType,
} from "@bufbuild/protobuf"
import type { CallOptions, ConnectError } from "@connectrpc/connect"
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

type RpcValidClient<T extends DescService> = {
  [K in keyof T["method"]]: T["method"][K] extends DescMethodUnary<infer I, infer O>
    ? (
        request: MessageInitShape<I>,
        options?: CallOptions,
      ) => Promise<MessageValidType<O>>
    : never
}

export const rpcClient = memoize(
  <T extends DescService>(service: T) =>
    createClient(service, rpcTransport) as RpcValidClient<T>,
)

export const rpcUnary = <I extends DescMessage, O extends DescMessage>(
  method: DescMethodUnary<I, O>,
) =>
  rpcClient(method.parent)[method.localName] as (
    request: MessageInitShape<I>,
    options?: CallOptions,
  ) => Promise<MessageValidType<O>>
