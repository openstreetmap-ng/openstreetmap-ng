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
import { queryParam } from "@lib/codecs"
import { ELEMENT_HISTORY_PAGE_SIZE } from "@lib/config"
import { tagsDiffStorage } from "@lib/local-storage"
import { focusObjects } from "@lib/map/layers/focus-layer"
import { convertRenderElementsData } from "@lib/map/render-objects"
import { type DataValid, Service } from "@lib/proto/element_pb"
import { ElementType } from "@lib/proto/shared_pb"
import { PageOrder, StandardPagination } from "@lib/standard-pagination"
import { Tags } from "@lib/tags"
import { setPageTitle } from "@lib/title"
import type { ReadonlySignal, Signal } from "@preact/signals"
import { t } from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"
import { useEffect, useRef } from "preact/hooks"

const HISTORY_LIMIT_MIN = 1
const HISTORY_LIMIT_MAX = 100

const getHistoryLimit = (limit: number | undefined) =>
  limit === undefined || !Number.isSafeInteger(limit)
    ? ELEMENT_HISTORY_PAGE_SIZE
    : Math.min(Math.max(limit, HISTORY_LIMIT_MIN), HISTORY_LIMIT_MAX)

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

const ElementHistoryEntry = ({ map, data }: { map: MaplibreMap; data: DataValid }) => {
  const { type, id, version } = data.ref
  const isLatest = !data.nextVersion
  const location = data.location

  const elementsRef = useRef<ReturnType<typeof convertRenderElementsData>>()
  const getElements = () => {
    elementsRef.current ??= convertRenderElementsData(data.context.render)
    return elementsRef.current
  }

  return (
    <div class="version-section section position-relative">
      <a
        class={`stretched-link link-underline link-underline-opacity-0-hover version-badge badge mb-3 ${isLatest ? "is-latest" : ""}`}
        href={`/${getElementTypeSlug(type)}/${id}/history/${version}`}
        onMouseEnter={() => focusObjects(map, getElements(), elementFocusPaint)}
        onMouseLeave={() => focusObjects(map)}
      >
        {t("browse.version")} {version}
      </a>

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
        diff={tagsDiffStorage.value && version > 1}
      />
    </div>
  )
}

const ElementHistorySidebar = ({
  map,
  type,
  id,
  limit,
}: {
  map: MaplibreMap
  type: ReadonlySignal<ElementTypeSlug>
  id: ReadonlySignal<bigint>
  limit: Signal<number | undefined>
}) => {
  const title = getPageTitle(type.value, id.toString())
  const pageSize = getHistoryLimit(limit.value)

  setPageTitle(title)

  // Effect: unfocus on unmount
  useEffect(() => () => focusObjects(map), [])

  return (
    <div class="sidebar-content">
      <div class="section pb-1">
        <SidebarHeader class="mb-1">
          <div class="d-flex flex-column gap-2">
            <h2 class="sidebar-title mb-0">{title}</h2>
            <div class="d-flex align-items-center flex-wrap gap-2">
              <div class="form-check ms-1">
                <label class="form-check-label">
                  <input
                    class="form-check-input"
                    type="checkbox"
                    autoComplete="off"
                    checked={tagsDiffStorage.value}
                    onChange={(e) => {
                      const checked = e.currentTarget.checked
                      tagsDiffStorage.value = checked
                    }}
                  />
                  {t("element.tags_diff_mode")}
                  <BTooltip
                    title={t("element.highlight_changed_tags_between_versions")}
                  >
                    <i class="bi bi-question-circle ms-1-5" />
                  </BTooltip>
                </label>
              </div>
              <label class="d-inline-flex align-items-center gap-2 mb-0 small text-body-secondary">
                {t("element.history_limit")}
                <input
                  class="form-control form-control-sm w-auto"
                  type="number"
                  min={HISTORY_LIMIT_MIN}
                  max={HISTORY_LIMIT_MAX}
                  step={1}
                  value={pageSize}
                  aria-label={t("element.history_limit")}
                  onChange={(e) => {
                    const value = e.currentTarget.valueAsNumber
                    if (!Number.isFinite(value)) return
                    const next = getHistoryLimit(value)
                    limit.value = next === ELEMENT_HISTORY_PAGE_SIZE ? undefined : next
                  }}
                />
              </label>
            </div>
          </div>
        </SidebarHeader>
      </div>

      <StandardPagination
        method={Service.method.getHistory}
        request={{
          element: { type: ElementType[type.value], id: id.value },
          tagsDiff: tagsDiffStorage.value,
          pageSize,
        }}
        urlKey="page"
        ariaLabel={t("alt.elements_page_navigation")}
        pageOrder={PageOrder.desc_range}
        onLoad={() => focusObjects(map)}
        small
        navClassBottom="mb-0"
        spinnerClass="pt-4"
      >
        {(resp) => (
          <div class="section p-0">
            <div>
              {resp.elements.map((entry) => (
                <ElementHistoryEntry
                  key={entry.ref.version}
                  map={map}
                  data={entry}
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
  query: { limit: queryParam.positiveInt() },
  Component: ElementHistorySidebar,
})
