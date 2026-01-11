import {
  getActionSidebar,
  SidebarHeader,
  switchActionSidebar,
} from "@index/_action-sidebar"
import { API_URL, MAP_QUERY_AREA_MAX_SIZE } from "@lib/config"
import { zoomPrecision } from "@lib/coords"
import { tRich } from "@lib/i18n"
import { boundsPadding, boundsToBounds, boundsToString } from "@lib/map/bounds"
import { LocationFilterControl } from "@lib/map/controls/location-filter"
import { qsEncode } from "@lib/qs"
import { setPageTitle } from "@lib/title"
import type { Bounds } from "@lib/types"
import {
  type ReadonlySignal,
  signal,
  useSignal,
  useSignalEffect,
} from "@preact/signals"
import { equal } from "@std/assert"
import { throttle } from "@std/async/unstable-throttle"
import { t } from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"
import { render } from "preact"
import { useRef } from "preact/hooks"

const ExportSidebar = ({
  map,
  sidebar,
  active,
}: {
  map: MaplibreMap
  sidebar: HTMLElement
  active: ReadonlySignal<boolean>
}) => {
  const bounds = useSignal<Bounds>()
  const boundsPrecision = useSignal(0)
  const locationFilterActive = useSignal(false)
  const locationFilter = useRef<LocationFilterControl>()

  const updateBoundsPrecision = () => {
    if (!active.peek()) return

    boundsPrecision.value = zoomPrecision(map.getZoom())
  }

  const updateBounds = () => {
    if (!active.peek()) return

    const newBounds = boundsToBounds(
      locationFilterActive.peek()
        ? (locationFilter.current?.getBounds() ?? map.getBounds())
        : map.getBounds(),
    )
    if (!equal(bounds.peek(), newBounds)) bounds.value = newBounds
  }

  // Effect: Bind map listeners and init state
  useSignalEffect(() => {
    if (!active.value) return

    switchActionSidebar(map, sidebar)
    setPageTitle(t("map.data_export.title"))

    map.on("zoomend", updateBoundsPrecision)
    map.on("moveend", updateBounds)

    updateBoundsPrecision()
    updateBounds()

    return () => {
      map.off("zoomend", updateBoundsPrecision)
      map.off("moveend", updateBounds)

      locationFilterActive.value = false
    }
  })

  // Effect: Enable/disable location filter control
  useSignalEffect(() => {
    if (!(active.value && locationFilterActive.value)) return

    if (!locationFilter.current) {
      locationFilter.current = new LocationFilterControl()
      locationFilter.current.addOnRenderHandler(
        throttle(updateBounds, 250, { ensureLastCall: true }),
      )
    }

    locationFilter.current.addTo(map, boundsPadding(map.getBounds(), -0.2))
    updateBounds()

    return () => {
      locationFilter.current!.remove()
      updateBounds()
    }
  })

  const b = bounds.value
  const bp = boundsPrecision.value

  let bboxQueryString = ""
  let isFormAvailable = false
  let minLonText = ""
  let minLatText = ""
  let maxLonText = ""
  let maxLatText = ""

  if (b) {
    const [minLon, minLat, maxLon, maxLat] = b
    bboxQueryString = qsEncode({ bbox: boundsToString(b) })
    isFormAvailable = (maxLon - minLon) * (maxLat - minLat) <= MAP_QUERY_AREA_MAX_SIZE
    minLonText = minLon.toFixed(bp)
    minLatText = minLat.toFixed(bp)
    maxLonText = maxLon.toFixed(bp)
    maxLatText = maxLat.toFixed(bp)
  }

  return (
    <div class="sidebar-content">
      <div class="section">
        <SidebarHeader title={t("map.data_export.title")} />

        <div class="export-container p-1 mb-2">
          <div class="d-flex justify-content-center mb-2">
            <input
              type="text"
              class="form-control"
              name="max_lat"
              title={t("map.export.max_lat")}
              autoComplete="off"
              disabled
              value={maxLatText}
            />
          </div>
          <div class="d-flex justify-content-between align-items-center mb-2">
            <input
              type="text"
              class="form-control"
              name="min_lon"
              title={t("map.export.min_lon")}
              autoComplete="off"
              disabled
              value={minLonText}
            />
            <i class="bi bi-compass-fill"></i>
            <input
              type="text"
              class="form-control"
              name="max_lon"
              title={t("map.export.max_lon")}
              autoComplete="off"
              disabled
              value={maxLonText}
            />
          </div>
          <div class="d-flex justify-content-center">
            <input
              type="text"
              class="form-control"
              name="min_lat"
              title={t("map.export.min_lat")}
              autoComplete="off"
              disabled
              value={minLatText}
            />
          </div>
        </div>

        <div class="form-check ms-1 mb-3">
          <label class="form-check-label">
            <input
              class="form-check-input"
              type="checkbox"
              autoComplete="off"
              checked={locationFilterActive.value}
              onChange={() =>
                (locationFilterActive.value = !locationFilterActive.value)
              }
            />
            {t("site.export.manually_select")}
          </label>
        </div>

        <div class="mb-3">
          {b &&
            (isFormAvailable ? (
              <a
                class="btn btn-primary w-100"
                href={`${API_URL}/api/0.6/map${bboxQueryString}`}
                target="_blank"
                rel="noopener"
              >
                {t("site.export.export_button")}
              </a>
            ) : (
              <div
                class="alert alert-warning"
                role="alert"
              >
                {t("site.export.too_large.body")}
              </div>
            ))}
        </div>

        <p>{t("site.export.too_large.advice")}</p>

        <ul class="mb-2">
          <li>
            <h6 class="mb-1">
              <img
                class="source-icon"
                src="/static/img/brand/overpass.webp"
                alt={t("alt.logo", { name: "Overpass" })}
                loading="lazy"
              />
              <a
                href={`https://overpass-api.de/api/map${bboxQueryString}`}
                target="_blank"
                rel="noopener"
              >
                {t("site.export.too_large.overpass.title")}
              </a>
            </h6>
            <p>{t("site.export.too_large.overpass.description")}</p>
          </li>

          <li>
            <h6 class="mb-1">
              <img
                class="source-icon"
                src="/static/img/favicon/256.webp"
                alt={t("alt.logo", { name: t("project_name") })}
                loading="lazy"
              />
              <a href="https://planet.openstreetmap.org">
                {t("site.export.too_large.planet.title")}
              </a>
            </h6>
            <p>{t("site.export.too_large.planet.description")}</p>
          </li>

          <li>
            <h6 class="mb-1">
              <img
                class="source-icon"
                src="/static/img/brand/geofabrik.webp"
                alt={t("alt.logo", { name: "Geofabrik" })}
                loading="lazy"
              />
              <a href="https://download.geofabrik.de">
                {t("site.export.too_large.geofabrik.title")}
              </a>
            </h6>
            <p>{t("site.export.too_large.geofabrik.description")}</p>
          </li>

          <li>
            <h6 class="mb-1">
              <a href="https://wiki.openstreetmap.org/wiki/Downloading_data">
                {t("site.export.too_large.other.title")}
              </a>
            </h6>
            <p class="mb-0">{t("site.export.too_large.other.description")}</p>
          </li>
        </ul>
      </div>

      <div class="section">
        <h4>{t("site.export.licence")}</h4>
        <p class="mb-2">
          {tRich("site.export.licence_details_html", {
            odbl_link: () => (
              <a
                href="https://opendatacommons.org/licenses/odbl/1-0/"
                target="_blank"
                rel="license noopener"
              >
                {t("site.export.odbl")}
              </a>
            ),
          })}
        </p>
        <p class="small text-end me-1 mb-2">
          <a
            href="/copyright"
            rel="license"
          >
            {t("layouts.learn_more")}
            <i class="bi bi-arrow-right-short ms-1"></i>
          </a>
        </p>
      </div>
    </div>
  )
}

export const getExportController = (map: MaplibreMap) => {
  const sidebar = getActionSidebar("export")
  const active = signal(false)

  render(
    <ExportSidebar
      map={map}
      sidebar={sidebar}
      active={active}
    />,
    sidebar,
  )

  return {
    load: () => {
      active.value = true
    },
    unload: () => {
      active.value = false
    },
  }
}
