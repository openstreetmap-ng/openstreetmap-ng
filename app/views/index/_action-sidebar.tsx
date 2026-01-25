import type {
  DescMessage,
  DescMethodUnary,
  MessageInitShape,
  MessageValidType,
} from "@bufbuild/protobuf"
import { fromBinary, type Message } from "@bufbuild/protobuf"
import type { GenMessage } from "@bufbuild/protobuf/codegenv2"
import { type CallOptions, Code, ConnectError } from "@connectrpc/connect"
import { IndexRoute } from "@index/index"
import { routerNavigate } from "@index/router"
import { useDisposeSignalEffect } from "@lib/dispose-scope"
import { connectErrorToMessage, rpcClient } from "@lib/rpc"
import {
  type ReadonlySignal,
  type Signal,
  useComputed,
  useSignal,
} from "@preact/signals"
import { assert } from "@std/assert"
import { t } from "i18next"
import type { ComponentChildren } from "preact"

// State machine for sidebar async resources
export type SidebarResource<T> =
  | { tag: "idle" }
  | { tag: "loading"; prev: T | null }
  | { tag: "ready"; data: T }
  | { tag: "error"; error: string; prev: T | null }
  | { tag: "not-found" }

type SidebarFetchResult<T> = {
  resource: Signal<SidebarResource<T>>
  data: ReadonlySignal<T | null>
}

const SidebarOverlaySpinner = () => (
  <output
    class="spinner-border text-body-secondary"
    aria-live="polite"
  >
    <span class="visually-hidden">{t("browse.start_rjs.loading")}</span>
  </output>
)

export const SidebarResourceBody = <T extends object>({
  resource,
  notFound,
  children,
}: {
  resource: ReadonlySignal<SidebarResource<T>>
  notFound?: () => ComponentChildren
  children: (data: T) => ComponentChildren
}) => {
  const r = resource.value

  switch (r.tag) {
    case "idle":
      return null
    case "loading":
      return r.prev ? (
        <div aria-busy="true">
          <div class="sidebar-loading-overlay">
            <div class="sidebar-loading-overlay-inner">
              <SidebarOverlaySpinner />
            </div>
          </div>
          <div
            class="opacity-50"
            inert
          >
            {children(r.prev)}
          </div>
        </div>
      ) : (
        <LoadingSpinner />
      )
    case "ready":
      return (
        <div>
          <div></div>
          <div>{children(r.data)}</div>
        </div>
      )
    case "error":
      return (
        <div
          class="alert alert-danger"
          role="alert"
        >
          {r.error}
        </div>
      )
    case "not-found":
      return notFound?.()
  }
}

const useSidebarRequest = <Req, Res extends object>(
  request: ReadonlySignal<Req | null>,
  call: (request: Req, signal: AbortSignal) => Promise<Res | null>,
  getErrorMessage: (reason: Error) => string = (e) => e.message,
): SidebarFetchResult<Res> => {
  const resource = useSignal<SidebarResource<Res>>({ tag: "idle" })

  useDisposeSignalEffect((scope) => {
    const req = request.value
    if (req === null) {
      resource.value = { tag: "idle" }
      return
    }

    const current = resource.peek()
    const prev =
      current.tag === "ready"
        ? current.data
        : (current.tag === "loading" || current.tag === "error") && current.prev
          ? current.prev
          : null

    resource.value = { tag: "loading", prev }

    call(req, scope.signal)
      .then((data) => {
        resource.value = data === null ? { tag: "not-found" } : { tag: "ready", data }
      })
      .catch((reason) => {
        if (scope.signal.aborted) return
        resource.value = { tag: "error", error: getErrorMessage(reason), prev }
      })
  })

  const data = useComputed(() =>
    resource.value.tag === "ready" ? resource.value.data : null,
  )
  return { resource, data }
}

/**
 * Hook for fetching sidebar data with unified state management.
 * Handles cancellation lifecycle, 404 detection, and protobuf decoding.
 *
 * @param url - Signal containing the URL to fetch, or null to reset to idle
 * @param schema - Protobuf schema for decoding the response
 * @returns Resource state and decoded data
 */
export const useSidebarFetch = <T extends object>(
  url: ReadonlySignal<string | null>,
  schema: GenMessage<T & Message>,
): SidebarFetchResult<T> => {
  return useSidebarRequest(url, async (urlValue, signal) => {
    const resp = await fetch(urlValue, { signal, priority: "high" })
    if (resp.status === 404) return null
    assert(resp.ok, `${resp.status} ${resp.statusText}`)
    const buffer = await resp.arrayBuffer()
    signal.throwIfAborted()
    return fromBinary(schema, new Uint8Array(buffer)) as T
  })
}

export const useSidebarRpc = <I extends DescMessage, O extends DescMessage>(
  request: ReadonlySignal<MessageInitShape<I> | null>,
  method: DescMethodUnary<I, O>,
): SidebarFetchResult<MessageValidType<O>> => {
  return useSidebarRequest(
    request,
    async (req, signal) => {
      try {
        const fn = rpcClient(method.parent)[method.localName] as (
          request: MessageInitShape<I>,
          options?: CallOptions,
        ) => Promise<MessageValidType<O>>
        return await fn(req, { signal })
      } catch (reason) {
        const err = ConnectError.from(reason)
        if (err.code === Code.NotFound) return null
        throw err
      }
    },
    (reason) => connectErrorToMessage(ConnectError.from(reason)),
  )
}

export const SidebarHeader = ({
  title,
  class: className = "mb-3",
  onClose = onCloseButtonClick,
  children,
}: {
  title?: ComponentChildren
  class?: string
  onClose?: () => void
  children?: ComponentChildren
}) => (
  <div class={`row g-1 ${className}`}>
    <div class="col">{title ? <h2 class="sidebar-title">{title}</h2> : children}</div>
    <div class="col-auto">
      <button
        class="sidebar-close-btn btn-close"
        aria-label={t("javascripts.close")}
        type="button"
        onClick={onClose}
      />
    </div>
  </div>
)

export const SidebarContent = <T extends object>({
  resource,
  notFound,
  children,
}: {
  resource: ReadonlySignal<SidebarResource<T>>
  notFound: () => string
  children: (data: T) => ComponentChildren
}) => {
  return (
    <div class="sidebar-content">
      <SidebarResourceBody
        resource={resource}
        notFound={() => (
          <div class="section">
            <SidebarHeader title={t("browse.not_found.title")} />
            <p>{notFound()}</p>
          </div>
        )}
      >
        {children}
      </SidebarResourceBody>
    </div>
  )
}

export const LoadingSpinner = () => (
  <div
    class="text-center mt-4"
    aria-live="polite"
    aria-busy="true"
  >
    <output class="spinner-border text-body-secondary">
      <span class="visually-hidden">{t("browse.start_rjs.loading")}</span>
    </output>
  </div>
)

/** On sidebar close button click, navigate to index */
const onCloseButtonClick = () => {
  console.debug("ActionSidebar: Close clicked")
  routerNavigate(IndexRoute)
}
