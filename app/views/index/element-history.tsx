import { SidebarHeader } from "@index/_action-sidebar"
import {
  ElementIdParam,
  ElementLocation,
  ElementMeta,
  ElementTypeParam,
  type ElementTypeSlug,
  elementFocusPaint,
  getElementTypeSlug,
} from "@index/element"
import { defineRoute } from "@index/router"
import { BTooltip } from "@lib/bootstrap"
import { tagsDiffStorage } from "@lib/local-storage"
import { focusObjects } from "@lib/map/layers/focus-layer"
import { convertRenderElementsData } from "@lib/map/render-objects"
import { type ElementData, ElementHistoryPageSchema } from "@lib/proto/shared_pb"
import { StandardPagination } from "@lib/standard-pagination"
import { Tags } from "@lib/tags"
import { setPageTitle } from "@lib/title"
import type { ReadonlySignal } from "@preact/signals"
import { t } from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"
import { useEffect, useRef } from "preact/hooks"

const getPageTitle = (type: ElementTypeSlug, id: string) => {
  switch (type) {
    case "node":
      return t("browse.node.history_title_html", { name: id })
    case "way":
      return t("browse.way.history_title_html", { name: id })
    case "relation":
      return t("browse.relation.history_title_html", { name: id })
  }
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
  const idText = data.id.toString()
  const typeText = getElementTypeSlug(data.type)
  const versionText = data.version.toString()
  const isLatest = data.nextVersion === undefined
  const location = data.location

  const elementsRef = useRef<ReturnType<typeof convertRenderElementsData>>()
  const getElements = () => {
    elementsRef.current ??= convertRenderElementsData(data.params!.render!)
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
}: {
  map: MaplibreMap
  type: ReadonlySignal<ElementTypeSlug>
  id: ReadonlySignal<bigint>
}) => {
  const title = getPageTitle(type.value, id.toString())

  setPageTitle(title)

  useEffect(() => {
    return () => focusObjects(map)
  }, [])

  return (
    <div class="sidebar-content">
      <div class="section pb-1">
        <SidebarHeader class="mb-1">
          <h2 class="sidebar-title">{title}</h2>
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

      <StandardPagination
        key={`${type}-${id}-${tagsDiffStorage.value}`}
        action={`/api/web/element/${type}/${id}/history?tags_diff=${tagsDiffStorage.value}`}
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
    </div>
  )
}

export const ElementHistoryRoute = defineRoute({
  id: "element-history",
  path: "/:type/:id/history",
  params: { type: ElementTypeParam, id: ElementIdParam },
  Component: ElementHistorySidebar,
})
