import { SidebarHeader } from "@index/_action-sidebar"
import { routerCtx } from "@index/router"
import { SidebarToggleControl } from "@index/sidebar/_toggle-button"
import { isLatitude, isLongitude } from "@lib/coords"
import { CopyField } from "@lib/copy-group"
import { useDisposeEffect } from "@lib/dispose-scope"
import { shareExportFormatStorage } from "@lib/local-storage"
import { boundsPadding } from "@lib/map/bounds"
import { LocationFilterControl } from "@lib/map/controls/location-filter"
import { exportMapImage } from "@lib/map/export-image"
import { activeBaseLayerId, addLayerEventHandler } from "@lib/map/layers/layers"
import { mainMap } from "@lib/map/main-map"
import { getMarkerIconElement, MARKER_ICON_ANCHOR } from "@lib/map/marker"
import {
  getInitialMapState,
  getMapEmbedHtml,
  getMapGeoUri,
  getMapLayersCode,
  getMapShortlink,
  type LonLatZoom,
  type MapState,
} from "@lib/map/state"
import { batch, effect, useComputed, useSignal, useSignalEffect } from "@preact/signals"
import { format as formatDate } from "@std/datetime/format"
import { t } from "i18next"
import type { LngLat, LngLatBounds, Map as MaplibreMap } from "maplibre-gl"
import { Marker } from "maplibre-gl"
import type { TargetedSubmitEvent } from "preact"
import { useRef } from "preact/hooks"

const SHARE_FORMATS = [
  { mimeType: "image/jpeg", suffix: ".jpg", label: "JPEG" },
  { mimeType: "image/png", suffix: ".png", label: "PNG" },
  { mimeType: "image/webp", suffix: ".webp", label: "WebP" },
] as const

let urlMarker: Marker | null = null

const ensureUrlMarker = (
  logText: string,
  map: MaplibreMap,
  lon: number,
  lat: number,
) => {
  let marker = urlMarker
  if (!marker) {
    marker = new Marker({
      anchor: MARKER_ICON_ANCHOR,
      element: getMarkerIconElement("blue", true),
      draggable: false,
    })
    marker.getElement().style.pointerEvents = "none"
    urlMarker = marker
  } else {
    const point = marker.getLngLat()
    if (point.lng === lon && point.lat === lat) return
  }

  console.debug(logText, [lon, lat])
  marker.setLngLat([lon, lat]).addTo(map)
}

const removeUrlMarker = () => {
  urlMarker?.remove()
  urlMarker = null
}

export const ShareSidebar = ({ close }: { close: () => void }) => {
  const map = mainMap.value!
  const shareMarkerEnabled = useSignal(false)
  const shareMarkerRef = useRef<Marker | null>(null)

  const locationFilterEnabled = useSignal(false)
  const locationFilterRef = useRef<LocationFilterControl | null>(null)

  const withAttribution = useSignal(true)
  const exporting = useSignal(false)

  const shareView = useSignal<LonLatZoom>()
  const shareLayersCode = useSignal<string>()
  const shareBounds = useSignal<LngLatBounds>()
  const shareMarkerLngLat = useSignal<LngLat | null>(null)

  const shareExportFileSuffix = useComputed(
    () =>
      SHARE_FORMATS.find((f) => f.mimeType === shareExportFormatStorage.value)!.suffix,
  )

  const shareMapState = useComputed(() => {
    const view = shareView.value
    if (!view) return null
    return { ...view, layersCode: shareLayersCode.value ?? "" } satisfies MapState
  })
  const linkValue = useComputed(() => {
    const state = shareMapState.value
    if (!state) return ""
    return getMapShortlink(state, shareMarkerLngLat.value)
  })
  const geoUriValue = useComputed(() => {
    const state = shareMapState.value
    if (!state) return ""
    return getMapGeoUri(state)
  })
  const embedValue = useComputed(() => {
    const state = shareMapState.value
    const bounds = shareBounds.value
    const baseLayerId = activeBaseLayerId.value
    if (!(state && bounds && baseLayerId)) return ""
    return getMapEmbedHtml(state, bounds, baseLayerId, shareMarkerLngLat.value)
  })

  const getMarkerLngLat = () => {
    if (!shareMarkerEnabled.value) return null
    return shareMarkerRef.current!.getLngLat()
  }

  const updateView = () => {
    batch(() => {
      const center = map.getCenter().wrap()
      const zoom = map.getZoom()
      shareView.value = {
        lon: center.lng,
        lat: center.lat,
        zoom,
      }
      shareBounds.value = map.getBounds()
    })
  }

  const updateMarkerLngLat = () => {
    shareMarkerLngLat.value = getMarkerLngLat()
  }

  const updateLayersCode = () => {
    shareLayersCode.value = getMapLayersCode(map)
  }

  useDisposeEffect((scope) => {
    scope.map(map, "moveend", updateView)
    updateView()
    updateMarkerLngLat()
    scope.defer(addLayerEventHandler(updateLayersCode))
    updateLayersCode()

    return () => () => {
      shareMarkerRef.current?.remove()
      locationFilterRef.current?.remove()
    }
  }, [])

  useSignalEffect(() => {
    let marker = shareMarkerRef.current
    if (!shareMarkerEnabled.value) {
      marker?.remove()
      updateMarkerLngLat()
      return
    }

    const lngLat = marker?.getLngLat() ?? map.getCenter()
    if (!marker) {
      marker = new Marker({
        anchor: MARKER_ICON_ANCHOR,
        element: getMarkerIconElement("blue", true),
        draggable: true,
      })
      shareMarkerRef.current = marker
      marker.on("dragend", updateMarkerLngLat)
    }

    marker.setLngLat(lngLat).addTo(map)
    updateMarkerLngLat()
  })

  useSignalEffect(() => {
    let locationFilter = locationFilterRef.current
    if (!locationFilterEnabled.value) {
      locationFilter?.remove()
      return
    }

    if (!locationFilter) {
      locationFilter = new LocationFilterControl()
      locationFilterRef.current = locationFilter
    }

    // By default, location filter is slightly smaller than the current view
    locationFilter.addTo(map, boundsPadding(map.getBounds(), -0.2))
  })

  const onExportSubmit = async (e: TargetedSubmitEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (exporting.value) return
    exporting.value = true

    try {
      const filterBounds = locationFilterEnabled.value
        ? locationFilterRef.current!.getBounds()
        : null

      const blob = await exportMapImage(
        shareExportFormatStorage.value,
        map,
        filterBounds,
        getMarkerLngLat(),
        withAttribution.value,
      )
      const url = URL.createObjectURL(blob)

      const now = new Date()
      const date = `${formatDate(now, "yyyy-MM-dd", { timeZone: "UTC" })} ${formatDate(now, "HH-mm-ss")}`

      const a = document.createElement("a")
      a.href = url
      a.download = `Map ${date}${shareExportFileSuffix.value}`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      exporting.value = false
    }
  }

  return (
    <div class="sidebar-content">
      <div class="section">
        <SidebarHeader
          title={t("javascripts.share.title")}
          class="mb-1"
          onClose={close}
        />

        <div class="form-check ms-1 mb-2">
          <label class="form-check-label d-block">
            <input
              class="form-check-input"
              type="checkbox"
              autoComplete="off"
              checked={shareMarkerEnabled.value}
              onChange={(e) => (shareMarkerEnabled.value = e.currentTarget.checked)}
            />
            {t("javascripts.share.include_marker")}
            <span class="text-body-tertiary ms-1">
              (
              <img
                class="marker-icon"
                src="/static/img/marker/blue.webp"
                alt={t("alt.marker.blue")}
              />
              )
            </span>
          </label>
        </div>

        <CopyField
          label={t("javascripts.share.long_link")}
          value={linkValue.value}
        />
        <CopyField
          label={t("javascripts.share.geo_uri")}
          value={geoUriValue.value}
        />
        <CopyField
          label={t("javascripts.share.embed")}
          value={embedValue.value}
        />
      </div>

      <form
        class="section"
        onSubmit={onExportSubmit}
      >
        <h4 class="mb-3">{t("javascripts.share.image")}</h4>

        <div class="form-check ms-1 mb-2">
          <label class="form-check-label d-block">
            <input
              class="form-check-input"
              type="checkbox"
              autoComplete="off"
              checked={locationFilterEnabled.value}
              onChange={(e) => (locationFilterEnabled.value = e.currentTarget.checked)}
            />
            {t("map.export.select_custom_region")}
          </label>
        </div>

        <div class="form-check ms-1 mb-3">
          <label class="form-check-label d-block">
            <input
              class="form-check-input"
              type="checkbox"
              checked={withAttribution.value}
              onChange={(e) => (withAttribution.value = e.currentTarget.checked)}
            />
            {t("map.export.include_attribution")}
          </label>
        </div>

        <label class="d-block form-label mb-3">
          {t("action.save_as")}
          <select
            class="form-select format-select mt-2"
            value={shareExportFormatStorage.value}
            onChange={(e) => {
              shareExportFormatStorage.value = e.currentTarget.value
            }}
          >
            {SHARE_FORMATS.map(({ mimeType, label }) => (
              <option
                key={mimeType}
                value={mimeType}
              >
                {label}
              </option>
            ))}
          </select>
        </label>

        <button
          class="btn btn-primary px-4 mb-2"
          type="submit"
          disabled={exporting.value}
        >
          {exporting.value ? t("state.preparing") : t("action.save_image")}
        </button>
        <p class="form-text">{t("map.export.exported_image_will_include")}</p>
      </form>
    </div>
  )
}

export class ShareSidebarToggleControl extends SidebarToggleControl {
  public constructor() {
    super("share", t("javascripts.share.title"))
  }

  public override onAdd(map: MaplibreMap) {
    const container = super.onAdd(map)

    effect(() => {
      const { queryParams } = routerCtx.value
      const mlonText = queryParams.mlon?.at(-1)
      const mlatText = queryParams.mlat?.at(-1)
      if (mlonText && mlatText) {
        const mlon = Number.parseFloat(mlonText)
        const mlat = Number.parseFloat(mlatText)
        if (isLongitude(mlon) && isLatitude(mlat)) {
          ensureUrlMarker("ShareSidebar: Initializing marker from URL", map, mlon, mlat)
        } else {
          removeUrlMarker()
        }
      } else if (queryParams.m !== undefined) {
        const { lon, lat } = getInitialMapState(map)
        ensureUrlMarker("ShareSidebar: Initializing marker at center", map, lon, lat)
      } else {
        removeUrlMarker()
      }
    })

    return container
  }
}
