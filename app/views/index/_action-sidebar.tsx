import { fromBinary, type Message } from "@bufbuild/protobuf"
import type { GenMessage } from "@bufbuild/protobuf/codegenv2"
import { routerNavigateStrict } from "@index/router"
import {
  type ReadonlySignal,
  type Signal,
  useComputed,
  useSignal,
  useSignalEffect,
} from "@preact/signals"
import { assert, assertExists } from "@std/assert"
import { t } from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"
import type { ComponentChildren } from "preact"
import { collapseNavbar } from "../navbar/navbar"

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
  refresh: () => void
}

/**
 * Hook for fetching sidebar data with unified state management.
 * Handles AbortController lifecycle, 404 detection, and protobuf decoding.
 *
 * @param url - Signal containing the URL to fetch, or null to reset to idle
 * @param schema - Protobuf schema for decoding the response
 * @param options - Optional callbacks (onSuccess)
 * @returns Object with resource signal and refresh function
 */
export const useSidebarFetch = <T extends object>(
  url: ReadonlySignal<string | null>,
  schema: GenMessage<T & Message>,
): SidebarFetchResult<T> => {
  const resource = useSignal<SidebarResource<T>>({ tag: "idle" })
  const refreshKey = useSignal(0)

  // Effect: Fetch lifecycle
  useSignalEffect(() => {
    const urlValue = url.value
    if (urlValue === null) {
      resource.value = { tag: "idle" }
      return
    }

    refreshKey.value

    // Capture prev for stale-while-revalidate
    const current = resource.peek()
    const prev =
      current.tag === "ready"
        ? current.data
        : (current.tag === "loading" || current.tag === "error") && current.prev
          ? current.prev
          : null

    resource.value = { tag: "loading", prev }
    const abortController = new AbortController()

    fetch(urlValue, {
      signal: abortController.signal,
      priority: "high",
    })
      .then(async (resp) => {
        if (resp.status === 404) {
          resource.value = { tag: "not-found" }
          return
        }
        assert(resp.ok, `${resp.status} ${resp.statusText}`)

        const buffer = await resp.arrayBuffer()
        abortController.signal.throwIfAborted()
        const data = fromBinary(schema, new Uint8Array(buffer)) as T

        resource.value = { tag: "ready", data }
      })
      .catch((err) => {
        if (err.name === "AbortError") return
        resource.value = { tag: "error", error: err.message, prev }
      })

    return () => abortController.abort()
  })

  // Derived: extract data when ready
  const data = useComputed(() =>
    resource.value.tag === "ready" ? resource.value.data : null,
  )

  const refresh = () => {
    refreshKey.value++
  }

  return { resource, data, refresh }
}

export const SidebarHeader = ({
  title,
  class: className = "mb-3",
  children,
}: {
  title?: ComponentChildren
  class?: string
  children?: ComponentChildren
}) => (
  <div class={`row g-1 ${className}`}>
    <div class="col">{title ? <h2 class="sidebar-title">{title}</h2> : children}</div>
    <div class="col-auto">
      <button
        class="sidebar-close-btn btn-close"
        aria-label={t("javascripts.close")}
        type="button"
        onClick={onCloseButtonClick}
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
  const r = resource.value

  return (
    <div class={`sidebar-content ${r.tag === "loading" && r.prev ? "opacity-50" : ""}`}>
      {(() => {
        switch (r.tag) {
          case "idle":
            return null
          case "loading":
            return r.prev ? children(r.prev) : <LoadingSpinner />
          case "ready":
            return children(r.data)
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
            return (
              <div class="section">
                <SidebarHeader title={t("browse.not_found.title")} />
                <p>{notFound()}</p>
              </div>
            )
        }
      })()}
    </div>
  )
}

export const LoadingSpinner = () => (
  <div class="text-center mt-4">
    <output class="spinner-border text-body-secondary">
      <span class="visually-hidden">{t("browse.start_rjs.loading")}</span>
    </output>
  </div>
)

const actionSidebars = document.querySelectorAll("div.action-sidebar")
const sidebarContainer = actionSidebars.length ? actionSidebars[0].parentElement : null

/** Get the action sidebar with the given class name */
export const getActionSidebar = (className: string) =>
  document.querySelector(`div.action-sidebar.${className}`)!

/** Switch the action sidebar with the given class name */
export const switchActionSidebar = (map: MaplibreMap, actionSidebar: HTMLElement) => {
  console.debug("ActionSidebar: Switching", actionSidebar.classList)
  assertExists(sidebarContainer)

  // Toggle all action sidebars
  for (const sidebar of actionSidebars) {
    const isTarget = sidebar === actionSidebar
    if (isTarget) {
      sidebarContainer.classList.toggle(
        "sidebar-overlay",
        sidebar.dataset.sidebarOverlay === "1",
      )
    }
    sidebar.classList.toggle("d-none", !isTarget)
  }

  map.resize()
  collapseNavbar()
}

/** On sidebar close button click, navigate to index */
const onCloseButtonClick = () => {
  console.debug("ActionSidebar: Close clicked")
  routerNavigateStrict("/")
}

/** Configure action sidebar events */
export const configureActionSidebar = (sidebar: Element) => {
  const closeButton = sidebar.querySelector(".sidebar-close-btn")
  closeButton?.addEventListener("click", onCloseButtonClick)
}
