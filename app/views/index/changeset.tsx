import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import {
  configureActionSidebar,
  getActionSidebar,
  LoadingSpinner,
  switchActionSidebar,
} from "@index/_action-sidebar"
import { ElementsListRow, ElementsSection, getElementTypeLabel } from "@index/element"
import { resolveDatetimeLazy } from "@lib/datetime-inputs"
import { makeBoundsMinimumSize } from "@lib/map/bounds"
import { type FocusLayerPaint, focusObjects } from "@lib/map/layers/focus-layer"
import {
  type PartialChangesetParams_Element as Element,
  PartialElementParams_ElementType as ElementType,
  PartialChangesetParamsSchema,
} from "@lib/proto/shared_pb"
import { configureReportButtons } from "@lib/report"
import { configureStandardForm } from "@lib/standard-form"
import { configureStandardPagination } from "@lib/standard-pagination"
import { configureTagsFormat } from "@lib/tags-format"
import { setPageTitle } from "@lib/title"
import type { OSMChangeset } from "@lib/types"
import {
  batch,
  type Signal,
  signal,
  useComputed,
  useSignal,
  useSignalEffect,
} from "@preact/signals"
import { assert } from "@std/assert"
import { t } from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"
import { render } from "preact"
import { useRef } from "preact/hooks"

const focusPaint: FocusLayerPaint = {
  "fill-opacity": 0,
  "line-color": "#f90",
  "line-opacity": 1,
  "line-width": 3,
}

const getChangesetElementsTitle = (type: ElementType) => {
  if (type === ElementType.node)
    // @ts-expect-error - i18next pluralization
    return (count: string) => t("browse.changeset.node", { count })
  if (type === ElementType.way)
    // @ts-expect-error - i18next pluralization
    return (count: string) => t("browse.changeset.way", { count })
  // @ts-expect-error - i18next pluralization
  return (count: string) => t("browse.changeset.relation", { count })
}

const ChangesetSidebar = ({
  map,
  active,
  id,
  sidebar,
}: {
  map: MaplibreMap
  active: Signal<boolean>
  id: Signal<string | null>
  sidebar: HTMLElement
}) => {
  const contentRef = useRef<HTMLDivElement>(null)
  const html = useSignal<string | null>(null)
  const loading = useSignal(false)
  const refreshKey = useSignal(0)

  // Derived: Parse params from fetched HTML
  const params = useComputed(() => {
    if (!html.value) return null
    const doc = new DOMParser().parseFromString(html.value, "text/html")
    const titleEl = doc.querySelector(".sidebar-title") as HTMLElement
    if (!titleEl?.dataset.params) return null
    return fromBinary(
      PartialChangesetParamsSchema,
      base64Decode(titleEl.dataset.params),
    )
  })

  const refocus = (initial = false) => {
    const p = params.value
    if (!p?.bounds.length) return
    const object: OSMChangeset = {
      type: "changeset",
      id: p.id,
      bounds: p.bounds.map((b) =>
        makeBoundsMinimumSize(map, [b.minLon, b.minLat, b.maxLon, b.maxLat]),
      ),
    }
    focusObjects(map, [object], focusPaint, null, { fitBounds: initial })
  }

  const reload = () => refreshKey.value++

  // Effect: Fetch changeset partial
  useSignalEffect(() => {
    refreshKey.value

    const cid = id.value
    if (!(active.value && cid)) {
      batch(() => {
        html.value = null
        loading.value = false
      })
      return
    }

    loading.value = true
    const abortController = new AbortController()
    fetch(`/partial/changeset/${cid}`, {
      signal: abortController.signal,
      priority: "high",
    })
      .then(async (resp) => {
        assert(resp.ok || resp.status === 404, `${resp.status} ${resp.statusText}`)
        html.value = await resp.text()
      })
      .catch((error) => {
        if (error.name === "AbortError") return
        html.value = `<div class="alert alert-danger">${error.message}</div>`
      })
      .finally(() => (loading.value = false))

    return () => abortController.abort()
  })

  // Effect: Initialize sidebar content
  useSignalEffect(() => {
    if (!(html.value && contentRef.current)) return

    const content = contentRef.current
    resolveDatetimeLazy(content)
    configureActionSidebar(sidebar)
    configureTagsFormat(content.querySelector("div.tags"))
    configureReportButtons(content)

    const titleEl = content.querySelector<HTMLElement>(".sidebar-title")!
    setPageTitle(titleEl.textContent)

    const disposePagination = configureStandardPagination(
      content.querySelector("div.changeset-comments-pagination"),
    )
    const disposeSubscription = configureStandardForm(
      content.querySelector("form.subscription-form"),
      reload,
    )
    const disposeComment = configureStandardForm(
      content.querySelector("form.comment-form"),
      reload,
    )

    return () => {
      disposePagination?.()
      disposeSubscription?.()
      disposeComment?.()
    }
  })

  // Effect: Map focus
  useSignalEffect(() => {
    if (!params.value?.bounds.length) {
      focusObjects(map)
      return
    }

    const onZoom = () => refocus()
    map.on("zoomend", onZoom)
    refocus(true)

    return () => {
      map.off("zoomend", onZoom)
      focusObjects(map)
    }
  })

  // Effect: Sidebar visibility
  useSignalEffect(() => {
    if (active.value) switchActionSidebar(map, sidebar)
  })

  return (
    <div ref={contentRef}>
      {loading.value && <LoadingSpinner />}

      <div dangerouslySetInnerHTML={{ __html: html.value ?? "" }} />

      {params.value && (
        <div class="elements mt-3">
          {(
            [
              ["nodes", ElementType.node],
              ["ways", ElementType.way],
              ["relations", ElementType.relation],
            ] as const
          ).map(([key, type]) => (
            <ElementsSection
              key={key}
              items={params.value![key]}
              title={getChangesetElementsTitle(type)}
              renderRow={(el) => (
                <ChangesetElementRow
                  element={el}
                  type={type}
                />
              )}
              keyFn={(el) => `${key}-${el.id}-${el.version}`}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export const getChangesetController = (map: MaplibreMap) => {
  const sidebar = getActionSidebar("changeset")
  const active = signal(false)
  const id = signal<string | null>(null)

  render(
    <ChangesetSidebar
      map={map}
      active={active}
      id={id}
      sidebar={sidebar}
    />,
    sidebar,
  )

  return {
    load: (matchGroups: Record<string, string>) => {
      batch(() => {
        id.value = matchGroups.id
        active.value = true
      })
    },
    unload: () => {
      active.value = false
    },
  }
}

const ChangesetElementRow = ({
  element,
  type,
}: {
  element: Element
  type: ElementType
}) => {
  const idStr = element.id.toString()
  const typeSlug = ElementType[type] as "node" | "way" | "relation"
  return (
    <ElementsListRow
      href={`/${typeSlug}/${idStr}`}
      icon={element.icon}
      class={element.visible ? "" : "deleted"}
      title={element.name || idStr}
      meta={
        <>
          <span>{getElementTypeLabel(type)}</span>
          {element.name && <span>{`#${idStr}`}</span>}
          <span aria-hidden="true">·</span>
          <a
            href={`/${typeSlug}/${idStr}/history/${element.version}`}
          >{`v${element.version}`}</a>
        </>
      }
    />
  )
}
