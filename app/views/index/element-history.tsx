import { BTooltip } from "@components/bootstrap-wrappers"
import { PageOrder, StandardPagination } from "@components/standard-pagination"
import { Tags } from "@components/tags"
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
import { focusObjects } from "@map/layers/focus-layer"
import { convertRenderElementsData } from "@map/render-objects"
import { batch, type ReadonlySignal, useComputed } from "@preact/signals"
import { type DataValid, Service } from "@proto/element_pb"
import { ElementType } from "@proto/shared_pb"
import { setPageTitle } from "@runtime/title"
import { tagsDiffStorage } from "@utils/local-storage"
import { queryParam } from "@utils/path-codecs"
import {
  currentUrlSignal,
  readUrlQueryParam,
  updateUrlQueryParam,
} from "@utils/url-state"
import { t } from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"
import { useEffect, useRef } from "preact/hooks"

const HISTORY_LIMITS = ["10", "25", "50", "100"] as const
const HISTORY_LIMIT_QUERY = queryParam.enum(HISTORY_LIMITS, { default: "10" })
const PAGE_QUERY = queryParam.positiveInt()

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
}: {
  map: MaplibreMap
  type: ReadonlySignal<ElementTypeSlug>
  id: ReadonlySignal<bigint>
}) => {
  const title = getPageTitle(type.value, id.toString())
  const limit = useComputed(() =>
    readUrlQueryParam("limit", HISTORY_LIMIT_QUERY, currentUrlSignal.value),
  )

  setPageTitle(title)

  // Effect: unfocus on unmount
  useEffect(() => () => focusObjects(map), [])

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
                onChange={(e) => {
                  const checked = e.currentTarget.checked
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

      <div class="section py-2">
        <label class="d-flex align-items-center gap-2">
          <span>{t("element.versions_per_page")}</span>
          <select
            class="form-select form-select-sm w-auto"
            value={limit.value}
            onChange={(e) => {
              const next = e.currentTarget.value as (typeof HISTORY_LIMITS)[number]
              if (next === limit.value) return
              batch(() => {
                updateUrlQueryParam("limit", HISTORY_LIMIT_QUERY, next, "push")
                updateUrlQueryParam("page", PAGE_QUERY, undefined, "replace")
              })
            }}
          >
            {HISTORY_LIMITS.map((value) => (
              <option
                key={value}
                value={value}
              >
                {value}
              </option>
            ))}
          </select>
        </label>
      </div>

      <StandardPagination
        method={Service.method.getHistory}
        request={{
          element: { type: ElementType[type.value], id: id.value },
          tagsDiff: tagsDiffStorage.value,
          limit: Number(limit.value),
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
  Component: ElementHistorySidebar,
})
