import {
  getActionSidebar,
  SidebarHeader,
  switchActionSidebar,
} from "@index/_action-sidebar"
import {
  ElementLocation,
  ElementMeta,
  elementFocusPaint,
  getElementTypeSlug,
} from "@index/element"
import { BTooltip } from "@lib/bootstrap"
import { tagsDiffStorage } from "@lib/local-storage"
import { focusObjects } from "@lib/map/layers/focus-layer"
import { convertRenderElementsData } from "@lib/map/render-objects"
import { type ElementData, ElementHistoryPageSchema } from "@lib/proto/shared_pb"
import { StandardPagination } from "@lib/standard-pagination"
import { Tags } from "@lib/tags"
import { setPageTitle } from "@lib/title"
import {
  type ReadonlySignal,
  signal,
  useComputed,
  useSignalEffect,
} from "@preact/signals"
import { t } from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"
import { render } from "preact"
import { useRef } from "preact/hooks"
import type { IndexController } from "./router"

const getHistoryTitle = (type: string, id: string) => {
  if (type === "node") return t("browse.node.history_title_html", { name: id })
  if (type === "way") return t("browse.way.history_title_html", { name: id })
  if (type === "relation") return t("browse.relation.history_title_html", { name: id })
  return t("layouts.history")
}

const ElementHistoryEntry = ({
  map,
  data,
  tagsDiff,
}: {
  map: MaplibreMap
  data: ElementData
  tagsDiff: boolean
}) => {
  const elementsRef = useRef<ReturnType<typeof convertRenderElementsData> | null>(null)
  const idText = data.id.toString()
  const typeText = getElementTypeSlug(data.type)
  const versionText = data.version.toString()
  const isLatest = data.nextVersion === undefined
  const location = data.location
  const params = data.params!
  const renderData = params.render!

  const getElements = () => {
    elementsRef.current ??= convertRenderElementsData(renderData)
    return elementsRef.current
  }

  return (
    <div class="version-section section position-relative">
      <a
        class="stretched-link"
        href={`/${typeText}/${idText}/history/${versionText}`}
        onMouseEnter={() => {
          focusObjects(map, getElements(), elementFocusPaint)
        }}
        onMouseLeave={() => focusObjects(map)}
      />
      <h3 class={`version-badge badge mb-3 ${isLatest ? "is-latest" : ""}`}>
        {t("browse.version")} {versionText}
      </h3>

      <ElementMeta data={data} />

      {location && (
        <ElementLocation
          map={map}
          location={location}
        />
      )}

      <Tags
        tags={data.tags}
        tagsOld={data.tagsOld}
        diff={tagsDiff}
      />
    </div>
  )
}

const ElementHistorySidebar = ({
  map,
  type,
  id,
  sidebar,
}: {
  map: MaplibreMap
  type: ReadonlySignal<string | null>
  id: ReadonlySignal<string | null>
  sidebar: HTMLElement
}) => {
  const title = useComputed(() => {
    const typeValue = type.value
    const idValue = id.value
    if (!(typeValue && idValue)) return t("layouts.history")
    return getHistoryTitle(typeValue, idValue)
  })

  // Effect: Page title
  useSignalEffect(() => {
    const typeValue = type.value
    const idValue = id.value
    if (!(typeValue && idValue)) return
    setPageTitle(title.value)
  })

  // Effect: Sidebar visibility and map focus
  useSignalEffect(() => {
    if (id.value) switchActionSidebar(map, sidebar)
    else focusObjects(map)
  })

  const typeValue = type.value
  const idValue = id.value

  return (
    <div class="sidebar-content">
      <div class="section pb-1">
        <SidebarHeader class="mb-1">
          <h2 class="sidebar-title">{title.value}</h2>
          <div class="form-check ms-1">
            <label class="form-check-label">
              <input
                class="form-check-input"
                type="checkbox"
                autoComplete="off"
                checked={tagsDiffStorage.value}
                onChange={(event) => {
                  const checked = (event.currentTarget as HTMLInputElement).checked
                  tagsDiffStorage.value = checked
                }}
              />
              {t("element.tags_diff_mode")}
              <BTooltip title={t("element.highlight_changed_tags_between_versions")}>
                <i class="bi bi-question-circle ms-1-5" />
              </BTooltip>
            </label>
          </div>
        </SidebarHeader>
      </div>

      {typeValue && idValue && (
        <StandardPagination
          key={`${typeValue}-${idValue}-${tagsDiffStorage.value}`}
          action={`/api/web/element/${typeValue}/${idValue}/history?tags_diff=${tagsDiffStorage.value}`}
          label={t("alt.elements_page_navigation")}
          pageOrder="desc-range"
          small={true}
          navClassBottom="mb-0"
          protobuf={ElementHistoryPageSchema}
          onLoad={() => {
            focusObjects(map)
          }}
        >
          {(page) => (
            <div class="section p-0">
              <div>
                {page.elements.map((entry) => (
                  <ElementHistoryEntry
                    key={entry.version.toString()}
                    map={map}
                    data={entry}
                    tagsDiff={tagsDiffStorage.value}
                  />
                ))}
              </div>
            </div>
          )}
        </StandardPagination>
      )}
    </div>
  )
}

/** Create a new element history controller */
export const getElementHistoryController = (map: MaplibreMap) => {
  const sidebar = getActionSidebar("element-history")
  const type = signal<string | null>(null)
  const id = signal<string | null>(null)

  render(
    <ElementHistorySidebar
      map={map}
      type={type}
      id={id}
      sidebar={sidebar}
    />,
    sidebar,
  )

  const controller: IndexController = {
    load: ({ type: typeValue, id: idValue }) => {
      type.value = typeValue
      id.value = idValue
    },
    unload: () => {
      type.value = null
      id.value = null
    },
  }
  return controller
}
