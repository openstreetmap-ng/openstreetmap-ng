import type { DescMessage, MessageValidType } from "@bufbuild/protobuf"
import { mount } from "@lib/mount"
import { fromBase64Valid } from "@lib/rpc"
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
    const state = fromBase64Valid(schema, root.dataset.state!)
    const props = state as Parameters<typeof Component>[0]
    render(h(Component, props), root)
  })
