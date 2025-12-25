import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import {
  configureActionSidebar,
  getActionSidebar,
  LoadingSpinner,
  switchActionSidebar,
} from "@index/_action-sidebar"
import { resolveDatetimeLazy } from "@lib/datetime-inputs"
import { type FocusLayerPaint, focusObjects } from "@lib/map/layers/focus-layer"
import { convertRenderElementsData } from "@lib/map/render-objects"
import {
  type PartialElementParams_Entry as ElementEntry,
  type ElementIcon,
  PartialElementParams_ElementType as ElementType,
  PartialElementParamsSchema,
} from "@lib/proto/shared_pb"
import { configureTagsFormat } from "@lib/tags-format"
import { setPageTitle } from "@lib/title"
import {
  type Signal,
  signal,
  useComputed,
  useSignal,
  useSignalEffect,
} from "@preact/signals"
import { assert } from "@std/assert"
import { memoize } from "@std/cache/memoize"
import { t } from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"
import { type ComponentChildren, Fragment, render } from "preact"
import { useRef } from "preact/hooks"

const THEME_COLOR = "#f60"
const focusPaint: FocusLayerPaint = {
  "fill-color": THEME_COLOR,
  "fill-opacity": 0.5,
  "line-color": THEME_COLOR,
  "line-opacity": 1,
  "line-width": 4,
  "circle-radius": 10,
  "circle-color": THEME_COLOR,
  "circle-opacity": 0.4,
  "circle-stroke-color": THEME_COLOR,
  "circle-stroke-opacity": 1,
  "circle-stroke-width": 3,
}

export const ELEMENTS_PER_PAGE = 15

// Pagination controls
const Pagination = ({
  page,
  totalPages,
}: {
  page: Signal<number>
  totalPages: number
}) => (
  <nav aria-label={t("alt.elements_page_navigation")}>
    <ul class="pagination pagination-sm pagination-2ch justify-content-end mb-0">
      {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
        <li
          class={`page-item ${p === page.value ? "active" : ""}`}
          key={p}
        >
          <button
            class="page-link"
            type="button"
            onClick={() => (page.value = p)}
          >
            {p}
          </button>
        </li>
      ))}
    </ul>
  </nav>
)

// Paginated element list section
export const ElementsSection = <T,>({
  items,
  title,
  renderRow,
  keyFn,
  class: extraClass,
}: {
  items: T[]
  title: (count: string) => string
  renderRow: (item: T) => ComponentChildren
  keyFn: (item: T) => string
  class?: string
}) => {
  if (!items.length) return null
  const page = useSignal(1)
  const totalPages = Math.ceil(items.length / ELEMENTS_PER_PAGE)
  const pageItems = items.slice(
    (page.value - 1) * ELEMENTS_PER_PAGE,
    page.value * ELEMENTS_PER_PAGE,
  )

  return (
    <div class={extraClass}>
      <h4 class="mt-3">{title(getPaginationCountLabel(page.value, items.length))}</h4>
      <div class="elements-list mb-2">
        <table class="table table-sm align-middle mb-0">
          <tbody>
            {pageItems.map((item) => (
              <Fragment key={keyFn(item)}>{renderRow(item)}</Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <Pagination
          page={page}
          totalPages={totalPages}
        />
      )}
    </div>
  )
}

const ElementSidebar = ({
  map,
  type,
  id,
  version,
  sidebar,
}: {
  map: MaplibreMap
  type: Signal<string | null>
  id: Signal<string | null>
  version: Signal<string | null>
  sidebar: HTMLElement
}) => {
  const html = useSignal<string | null>(null)
  const loading = useSignal(false)
  const contentRef = useRef<HTMLDivElement>(null)

  // Derived: Parse params from fetched HTML
  const params = useComputed(() => {
    if (!html.value) return null
    const doc = new DOMParser().parseFromString(html.value, "text/html")
    const sidebarContent = doc.querySelector(".sidebar-content") as HTMLElement
    if (!sidebarContent?.dataset.params) return null
    return fromBinary(
      PartialElementParamsSchema,
      base64Decode(sidebarContent.dataset.params),
    )
  })

  // Effect: Fetch element partial
  useSignalEffect(() => {
    const etype = type.value
    const eid = id.value
    const v = version.value

    if (!(etype && eid)) {
      html.value = null
      loading.value = false
      return
    }

    loading.value = true
    const abortController = new AbortController()
    const url = v ? `/partial/${etype}/${eid}/history/${v}` : `/partial/${etype}/${eid}`

    const fetchPartial = async () => {
      try {
        const resp = await fetch(url, {
          signal: abortController.signal,
          priority: "high",
        })
        assert(resp.ok || resp.status === 404, `${resp.status} ${resp.statusText}`)

        const respText = await resp.text()
        abortController.signal.throwIfAborted()
        html.value = respText
      } catch (error) {
        if (error.name === "AbortError") return
        html.value = `<div class="alert alert-danger">${error.message}</div>`
      } finally {
        if (!abortController.signal.aborted) loading.value = false
      }
    }

    fetchPartial()
    return () => abortController.abort()
  })

  // Effect: Initialize sidebar content
  useSignalEffect(() => {
    if (!(html.value && contentRef.current)) return

    const content = contentRef.current
    resolveDatetimeLazy(content)
    configureActionSidebar(sidebar)

    const sidebarContent = content.querySelector("div.sidebar-content")!
    const sidebarTitleEl = sidebarContent.querySelector(".sidebar-title")!
    setPageTitle(sidebarTitleEl.textContent)

    configureTagsFormat(content.querySelector("div.tags"))

    const locationBtn = content.querySelector(
      ".location-container button",
    ) as HTMLButtonElement | null
    if (!locationBtn) return

    const onLocClick = () => {
      const { lon, lat } = locationBtn.dataset
      map.flyTo({
        center: [Number.parseFloat(lon!), Number.parseFloat(lat!)],
        zoom: Math.max(map.getZoom(), 15),
      })
    }
    locationBtn.addEventListener("click", onLocClick)
    return () => locationBtn.removeEventListener("click", onLocClick)
  })

  // Effect: Map focus
  useSignalEffect(() => {
    if (!params.value?.render) {
      focusObjects(map)
      return
    }

    const elements = convertRenderElementsData(params.value.render)
    focusObjects(map, elements, focusPaint)
    return () => focusObjects(map)
  })

  // Effect: Sidebar visibility
  useSignalEffect(() => {
    if (id.value) switchActionSidebar(map, sidebar)
  })

  return (
    <div ref={contentRef}>
      {loading.value && <LoadingSpinner />}

      <div dangerouslySetInnerHTML={{ __html: html.value ?? "" }} />

      {params.value && (
        <div class="elements mt-3">
          <ElementsSection
            items={params.value.parents}
            title={(count) => `${t("browse.part_of")} (${count})`}
            renderRow={(el) => <ElementRow element={el} />}
            keyFn={(el) => `${el.type}-${el.id}-${el.role ?? ""}`}
          />
          <ElementsSection
            items={params.value.members}
            title={(count) =>
              params.value!.type === ElementType.way
                ? // @ts-expect-error
                  t("browse.changeset.node", { count })
                : `${t("browse.relation.members")} (${count})`
            }
            renderRow={(el) => <ElementRow element={el} />}
            keyFn={(el) => `${el.type}-${el.id}-${el.role ?? ""}`}
          />
        </div>
      )}
    </div>
  )
}

export const getElementController = (map: MaplibreMap) => {
  const sidebar = getActionSidebar("element")
  const type = signal<string | null>(null)
  const id = signal<string | null>(null)
  const version = signal<string | null>(null)

  render(
    <ElementSidebar
      map={map}
      type={type}
      id={id}
      version={version}
      sidebar={sidebar}
    />,
    sidebar,
  )

  return {
    load: (matchGroups: Record<string, string>) => {
      type.value = matchGroups.type
      id.value = matchGroups.id
      version.value = matchGroups.version ?? null
    },
    unload: () => {
      id.value = null
    },
  }
}

export const ElementsListRow = ({
  href,
  icon,
  title,
  meta,
  class: extraClass,
}: {
  href: string
  icon: ElementIcon | undefined
  title: ComponentChildren
  meta: ComponentChildren
  class?: string
}) => (
  <tr class={extraClass}>
    <td>
      {icon && (
        <img
          loading="lazy"
          src={`/static/img/element/${icon.icon}`}
          title={icon.title}
          aria-hidden="true"
        />
      )}
    </td>

    <td>
      <div class="element-row-title">
        <a href={href}>
          <bdi>{title}</bdi>
        </a>
      </div>
      <div class="element-row-meta">{meta}</div>
    </td>
  </tr>
)

const ElementRow = ({ element }: { element: ElementEntry }) => {
  const idStr = element.id.toString()
  const href = `/${ElementType[element.type]}/${idStr}`

  return (
    <ElementsListRow
      href={href}
      icon={element.icon}
      title={element.name || idStr}
      meta={
        <>
          <span>{getElementTypeLabel(element.type)}</span>
          {element.name && <span>{`#${idStr}`}</span>}
          {element.role && (
            <>
              <span aria-hidden="true"> · </span>
              <span>{element.role}</span>
            </>
          )}
        </>
      }
    />
  )
}

export const getElementTypeLabel = memoize((type: ElementType) => {
  if (type === ElementType.node) return t("javascripts.query.node")
  if (type === ElementType.way) return t("javascripts.query.way")
  return t("javascripts.query.relation")
})

export const getPaginationCountLabel = (page: number, totalItems: number) => {
  if (totalItems > ELEMENTS_PER_PAGE) {
    const from = (page - 1) * ELEMENTS_PER_PAGE + 1
    const to = Math.min(page * ELEMENTS_PER_PAGE, totalItems)
    return t("pagination.range", {
      x: `${from}-${to}`,
      y: totalItems,
    })
  }
  return totalItems.toString()
}

/** Initialize element content for version sections in element history */
export const initializeElementContent = (map: MaplibreMap, container: Element) => {
  configureTagsFormat(container.querySelector("div.tags"))

  const locationButton = container.querySelector(
    ".location-container button",
  ) as HTMLButtonElement | null

  const onLocationClick = locationButton
    ? () => {
        const { lon, lat } = locationButton.dataset
        map.flyTo({
          center: [Number.parseFloat(lon!), Number.parseFloat(lat!)],
          zoom: Math.max(map.getZoom(), 15),
        })
      }
    : null

  if (onLocationClick) {
    locationButton!.addEventListener("click", onLocationClick)
  }

  const params = fromBinary(
    PartialElementParamsSchema,
    base64Decode((container as HTMLElement).dataset.params!),
  )

  return [
    params.render!,
    () => {
      if (onLocationClick) {
        locationButton!.removeEventListener("click", onLocationClick)
      }
    },
  ] as const
}
