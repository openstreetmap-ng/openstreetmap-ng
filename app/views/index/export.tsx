import { SidebarHeader } from "@index/_action-sidebar"
import { defineRoute } from "@index/router"
import { API_URL, MAP_QUERY_AREA_MAX_SIZE } from "@lib/config"
import { zoomPrecision } from "@lib/coords"
import { useDisposeEffect, useDisposeSignalEffect } from "@lib/dispose-scope"
import { tRich } from "@lib/i18n"
import { boundsEqual, boundsPadding, boundsSize, boundsToString } from "@lib/map/bounds"
import { LocationFilterControl } from "@lib/map/controls/location-filter"
import { qsEncode } from "@lib/qs"
import { setPageTitle } from "@lib/title"
import { useSignal } from "@preact/signals"
import { t } from "i18next"
import type { LngLatBounds, Map as MaplibreMap } from "maplibre-gl"
import { useRef } from "preact/hooks"

const ExportRouteComponent = ({ map }: { map: MaplibreMap }) => {
  setPageTitle(t("map.data_export.title"))

  const bounds = useSignal<LngLatBounds>()
  const boundsPrecision = useSignal(0)
  const locationFilterActive = useSignal(false)
  const locationFilter = useRef<LocationFilterControl>()

  const updateBoundsPrecision = () => {
    boundsPrecision.value = zoomPrecision(map.getZoom())
  }

  const updateBounds = () => {
    const newBounds = locationFilterActive.peek()
      ? (locationFilter.current?.getBounds() ?? map.getBounds())
      : map.getBounds()
    if (!boundsEqual(bounds.peek(), newBounds)) bounds.value = newBounds
  }

  // Effect: bind map listeners and init state.
  useDisposeEffect((scope) => {
    scope.map(map, "zoomend", updateBoundsPrecision)
    scope.map(map, "moveend", updateBounds)
    scope.defer(() => {
      locationFilterActive.value = false
    })

    updateBoundsPrecision()
    updateBounds()
  }, [])

  // Effect: enable/disable location filter control.
  useDisposeSignalEffect((scope) => {
    if (!locationFilterActive.value) return

    const control = new LocationFilterControl()
    locationFilter.current = control
    control.addOnRenderHandler(scope.throttle(250, () => updateBounds()))

    // By default, location filter is slightly smaller than the current view.
    control.addTo(map, boundsPadding(map.getBounds(), -0.2))
    updateBounds()

    scope.defer(() => {
      control.remove()
      locationFilter.current = undefined
      updateBounds()
    })
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
    bboxQueryString = qsEncode({ bbox: boundsToString(b) })
    isFormAvailable = boundsSize(b) <= MAP_QUERY_AREA_MAX_SIZE

    const [[minLon, minLat], [maxLon, maxLat]] = b.toArray()
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

export const ExportRoute = defineRoute({
  id: "export",
  path: "/export",
  Component: ExportRouteComponent,
})
