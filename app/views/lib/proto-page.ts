import type { DescMessage, MessageValidType } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import { mount } from "@lib/mount"
import { fromBinaryValid } from "@lib/rpc"
import { type ComponentChildren, h, render } from "preact"

type ProtoPageComponent<Schema extends DescMessage> = (
  props: Omit<MessageValidType<Schema>, "key" | "ref">,
) => ComponentChildren

export const mountProtoPage = <Schema extends DescMessage>(
  schema: Schema,
  Component: ProtoPageComponent<Schema>,
) =>
  mount(schema.typeName, () => {
    const root = document.querySelector<HTMLElement>("[data-page-root]")!
    const state = fromBinaryValid(schema, base64Decode(root.dataset.state!))
    const props = state as Parameters<typeof Component>[0]
    render(h(Component, props), root)
  })
