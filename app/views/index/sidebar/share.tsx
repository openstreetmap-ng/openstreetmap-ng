import { CopyField } from "@components/copy-group"
import { SidebarHeader } from "@index/_action-sidebar"
import { routerCtx } from "@index/router"
import { SidebarToggleControl } from "@index/sidebar/_toggle-button"
import { boundsPadding } from "@map/bounds"
import { LocationFilterControl } from "@map/controls/location-filter"
import {
  exportMapImage,
  getRenderMapExportUrl,
  type RenderExportFormat,
} from "@map/export-image"
import { activeBaseLayerId, addLayerEventHandler } from "@map/layers/layers"
import { mainMap } from "@map/main-map"
import { getMarkerIconElement, MARKER_ICON_ANCHOR } from "@map/marker"
import {
  getInitialMapState,
  getMapEmbedHtml,
  getMapGeoUri,
  getMapLayersCode,
  getMapShortlink,
  type LonLatZoom,
  type MapState,
} from "@map/state"
import { batch, effect, useComputed, useSignal, useSignalEffect } from "@preact/signals"
import { format as formatDate } from "@std/datetime/format"
import { tryParseLonLat } from "@utils/coords"
import { useDisposeEffect } from "@utils/dispose-scope"
import { shareExportFormatStorage } from "@utils/local-storage"
import { t } from "i18next"
import type { LngLat, LngLatBounds, Map as MaplibreMap } from "maplibre-gl"
import { Marker } from "maplibre-gl"
import type { SubmitEventHandler } from "preact"
import { useRef } from "preact/hooks"

type RasterShareFormat = {
  kind: "raster"
  mimeType: string
  suffix: string
  label: string
}

type RenderShareFormat = {
  kind: "render"
  mimeType: string
  suffix: string
  label: string
  format: RenderExportFormat
}

type ShareFormat = RasterShareFormat | RenderShareFormat

const SHARE_FORMATS = [
  { kind: "raster", mimeType: "image/jpeg", suffix: ".jpg", label: "JPEG" },
  { kind: "raster", mimeType: "image/png", suffix: ".png", label: "PNG" },
  { kind: "raster", mimeType: "image/webp", suffix: ".webp", label: "WebP" },
  {
    kind: "render",
    mimeType: "image/svg+xml",
    suffix: ".svg",
    label: "SVG",
    format: "svg",
  },
  {
    kind: "render",
    mimeType: "application/pdf",
    suffix: ".pdf",
    label: "PDF",
    format: "pdf",
  },
] satisfies readonly ShareFormat[]
const DEFAULT_SHARE_FORMAT = SHARE_FORMATS[1]!
const getShareFormat = (mimeType: string) =>
  SHARE_FORMATS.find((f) => f.mimeType === mimeType) ?? DEFAULT_SHARE_FORMAT

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
  const shareMarkerRef = useRef<Marker>(null)

  const locationFilterEnabled = useSignal(false)
  const locationFilterRef = useRef<LocationFilterControl>(null)

  const withAttribution = useSignal(true)
  const exporting = useSignal(false)

  const shareView = useSignal<LonLatZoom>()
  const shareLayersCode = useSignal<string>()
  const shareBounds = useSignal<LngLatBounds>()
  // null = marker disabled, LngLat = marker at that position. The single signal
  // serves both as the "is the marker enabled" discriminator and the position
  // payload, avoiding a redundant boolean shadow.
  const shareMarkerLngLat = useSignal<LngLat | null>(null)

  const shareExportFormat = useComputed(() =>
    getShareFormat(shareExportFormatStorage.value),
  )
  const shareExportFileSuffix = useComputed(() => shareExportFormat.value.suffix)

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

  const updateLayersCode = () => (shareLayersCode.value = getMapLayersCode(map))

  useDisposeEffect((scope) => {
    scope.map(map, "moveend", updateView)
    updateView()
    scope.defer(addLayerEventHandler(updateLayersCode))
    updateLayersCode()

    return () => {
      shareMarkerRef.current?.remove()
      locationFilterRef.current?.remove()
    }
  }, [])

  useSignalEffect(() => {
    const lngLat = shareMarkerLngLat.value
    let marker = shareMarkerRef.current
    if (lngLat === null) {
      marker?.remove()
      return
    }
    if (!marker) {
      marker = new Marker({
        anchor: MARKER_ICON_ANCHOR,
        element: getMarkerIconElement("blue", true),
        draggable: true,
      })
      shareMarkerRef.current = marker
      marker.on("dragend", () => {
        shareMarkerLngLat.value = marker!.getLngLat()
      })
    }
    marker.setLngLat(lngLat).addTo(map)
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

  const onExportSubmit: SubmitEventHandler<HTMLFormElement> = async (e) => {
    e.preventDefault()
    if (exporting.value) return
    exporting.value = true

    try {
      const filterBounds = locationFilterEnabled.value
        ? locationFilterRef.current!.getBounds()
        : null

      const now = new Date()
      const date = `${formatDate(now, "yyyy-MM-dd", { timeZone: "UTC" })} ${formatDate(now, "HH-mm-ss")}`
      const exportFormat = getShareFormat(shareExportFormatStorage.value)

      if (exportFormat.kind === "render") {
        const a = document.createElement("a")
        a.href = getRenderMapExportUrl(exportFormat.format, map, filterBounds)
        a.download = `Map ${date}${shareExportFileSuffix.value}`
        a.click()
        return
      }

      const blob = await exportMapImage(
        exportFormat.mimeType,
        map,
        filterBounds,
        shareMarkerLngLat.peek(),
        withAttribution.value,
      )
      const url = URL.createObjectURL(blob)

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
              checked={shareMarkerLngLat.value !== null}
              onChange={(e) => {
                shareMarkerLngLat.value = e.currentTarget.checked
                  ? map.getCenter()
                  : null
              }}
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
            onChange={(e) => (shareExportFormatStorage.value = e.currentTarget.value)}
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

export class ShareSidebarControl extends SidebarToggleControl {
  public constructor() {
    super("share", t("javascripts.share.title"))
  }

  public override onAdd(map: MaplibreMap) {
    const container = super.onAdd(map)

    effect(() => {
      const { queryParams } = routerCtx.value
      const location = tryParseLonLat(
        queryParams.mlon?.at(-1),
        queryParams.mlat?.at(-1),
      )
      if (location) {
        ensureUrlMarker(
          "ShareSidebar: Initializing marker from URL",
          map,
          location[0],
          location[1],
        )
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
