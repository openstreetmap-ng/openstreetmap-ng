import { t } from "i18next"
import type {
  GeoJSONSource,
  LngLat,
  LngLatBounds,
  Map as MaplibreMap,
} from "maplibre-gl"
import { boundsIntersect, boundsIntersection, boundsToString } from "./bounds"
import { loadMapImage } from "./image"
import {
  addMapLayer,
  emptyFeatureCollection,
  type LayerId,
  layersConfig,
  removeMapLayer,
} from "./layers/layers"

const LAYER_ID = "export-image" as LayerId
layersConfig.set(LAYER_ID, {
  specification: {
    type: "geojson",
    data: emptyFeatureCollection,
  },
  layerTypes: ["symbol"],
  layerOptions: {
    layout: {
      "icon-image": "marker-blue",
      "icon-size": 41 / 128,
      "icon-padding": 0,
      "icon-anchor": "bottom",
    },
  },
  priority: 200,
})

// https://developer.mozilla.org/en-US/docs/Web/API/HTMLCanvasElement/toBlob#quality
const IMAGE_QUALITY = 0.98
const SVG_MIME_TYPE = "image/svg+xml"
const PDF_MIME_TYPE = "application/pdf"
const RENDER_EXPORT_FORMATS = new Map([
  [SVG_MIME_TYPE, "svg"],
  [PDF_MIME_TYPE, "pdf"],
])
const EARTH_RADIUS = 6378137
const PRINT_METERS_PER_PIXEL = 1 / (92 * 39.3701)
const STANDARD_PIXEL_SIZE = 0.00028
const MAX_RENDER_AREA = 4_000_000 * STANDARD_PIXEL_SIZE ** 2
const MAX_MERCATOR_LATITUDE = 85.05112878

export const exportMapImage = async (
  mimeType: string,
  map: MaplibreMap,
  filterBounds: LngLatBounds | null,
  markerLngLat: LngLat | null,
  attribution: boolean,
) => {
  const renderFormat = RENDER_EXPORT_FORMATS.get(mimeType)
  if (renderFormat) return await exportRenderedMap(renderFormat, map, filterBounds)

  const exportCanvas = await renderMapCanvas(
    map,
    filterBounds,
    markerLngLat,
    attribution,
  )

  return await exportCanvasToBlob(exportCanvas, mimeType)
}

const exportRenderedMap = async (
  format: string,
  map: MaplibreMap,
  filterBounds: LngLatBounds | null,
) => {
  const mapBounds = map.getBounds()
  const exportBounds =
    filterBounds && boundsIntersect(mapBounds, filterBounds)
      ? boundsIntersection(mapBounds, filterBounds)
      : mapBounds
  const params = new URLSearchParams({
    bbox: boundsToString(exportBounds, 7),
    scale: getRenderScale(map, exportBounds).toString(),
    format,
  })
  const response = await fetch(`/api/web/map/export?${params}`)
  if (!response.ok) {
    throw new Error((await response.text()) || "Failed to export the map image")
  }
  return await response.blob()
}

const getRenderScale = (map: MaplibreMap, exportBounds: LngLatBounds) => {
  const scale = getCurrentMapScale(map)
  const minScale = getMinRenderScale(exportBounds)
  return scale < minScale ? roundScale(minScale) : scale
}

const getCurrentMapScale = (map: MaplibreMap) => {
  const bounds = map.getBounds().adjustAntiMeridian()
  const centerLat = bounds.getCenter().lat
  const halfWorldMeters =
    EARTH_RADIUS * Math.PI * Math.cos((centerLat * Math.PI) / 180)
  const meters = (halfWorldMeters * (bounds.getEast() - bounds.getWest())) / 180
  const pixelsPerMeter = map.getCanvas().clientWidth / meters
  const scale = Math.round(1 / (pixelsPerMeter * PRINT_METERS_PER_PIXEL))
  return Number.isFinite(scale) ? Math.max(1, scale) : 1
}

const getMinRenderScale = (bounds: LngLatBounds) => {
  const adjusted = bounds.adjustAntiMeridian()
  const southWest = projectMercator(adjusted.getSouthWest())
  const northEast = projectMercator(adjusted.getNorthEast())
  const area = Math.abs(northEast.x - southWest.x) * Math.abs(northEast.y - southWest.y)
  const scale = Math.floor(Math.sqrt(area / MAX_RENDER_AREA))
  return Number.isFinite(scale) ? Math.max(1, scale) : 1
}

const projectMercator = (lngLat: LngLat) => {
  const lat = Math.max(
    -MAX_MERCATOR_LATITUDE,
    Math.min(MAX_MERCATOR_LATITUDE, lngLat.lat),
  )
  const lonRad = (lngLat.lng * Math.PI) / 180
  const latRad = (lat * Math.PI) / 180
  return {
    x: EARTH_RADIUS * lonRad,
    y: EARTH_RADIUS * Math.log(Math.tan(Math.PI / 4 + latRad / 2)),
  }
}

const roundScale = (scale: number) => {
  const precision = 5 * 10 ** (Math.floor(Math.LOG10E * Math.log(scale)) - 2)
  return precision * Math.ceil(scale / precision)
}

const renderMapCanvas = async (
  map: MaplibreMap,
  filterBounds: LngLatBounds | null,
  markerLngLat: LngLat | null,
  attribution: boolean,
) => {
  const mapBounds = map.getBounds()

  // Render marker onto the map
  if (
    markerLngLat &&
    mapBounds.contains(markerLngLat) &&
    (!filterBounds || filterBounds.contains(markerLngLat))
  ) {
    console.debug("ExportImage: Rendering marker")
    const source = map.getSource<GeoJSONSource>(LAYER_ID)!
    await new Promise<void>((resolve) => {
      loadMapImage(map, "marker-blue", () => {
        source.setData({
          type: "Feature",
          properties: {},
          geometry: {
            type: "Point",
            coordinates: [markerLngLat.lng, markerLngLat.lat],
          },
        })
        addMapLayer(map, LAYER_ID)
        void map.once("render", () => {
          let framesDelay = 3
          const tryResolve = () => {
            if (!framesDelay) return resolve()
            framesDelay--
            requestAnimationFrame(tryResolve)
          }
          requestAnimationFrame(tryResolve)
        })
      })
    })
    removeMapLayer(map, LAYER_ID)
    source.setData(emptyFeatureCollection)
  }

  const sourceCanvas = map.getCanvas()
  console.debug(
    "ExportImage: Exporting",
    [sourceCanvas.width, sourceCanvas.height],
  )
  let exportCanvas = document.createElement("canvas")
  exportCanvas.width = sourceCanvas.width
  exportCanvas.height = sourceCanvas.height
  let ctx = exportCanvas.getContext("2d", { alpha: false })!
  ctx.drawImage(sourceCanvas, 0, 0)

  if (filterBounds) {
    console.debug("ExportImage: Filtering bounds", { mapBounds, filterBounds })
    const { top, left, bottom, right } = getImageTrim(
      map,
      exportCanvas.width,
      exportCanvas.height,
      mapBounds,
      filterBounds,
    )
    const trimCanvas = document.createElement("canvas")
    trimCanvas.width = exportCanvas.width - (left + right)
    trimCanvas.height = exportCanvas.height - (top + bottom)
    ctx = trimCanvas.getContext("2d", { alpha: false })!
    ctx.drawImage(
      exportCanvas,
      left,
      top,
      trimCanvas.width,
      trimCanvas.height,
      0,
      0,
      trimCanvas.width,
      trimCanvas.height,
    )
    exportCanvas = trimCanvas
  }
  if (attribution) {
    const attributionText = `© ${t("javascripts.map.openstreetmap_contributors")}`
    const fontSize = Math.round(window.devicePixelRatio * 16)

    const ctx = exportCanvas.getContext("2d", { alpha: false })!
    ctx.font = `500 ${fontSize}px sans-serif`
    ctx.textAlign = "left"
    ctx.textBaseline = "top"

    const textMetrics = ctx.measureText(attributionText)
    const textWidth = textMetrics.width
    const textHeight = fontSize * 0.9

    const padding = Math.round(window.devicePixelRatio * 10)
    const xPos = exportCanvas.width - textWidth - padding * 2
    const yPos = exportCanvas.height - textHeight - padding * 2

    ctx.fillStyle = "white"
    ctx.fillRect(xPos, yPos, textWidth + padding * 2, textHeight + padding * 2)
    ctx.fillStyle = "black"
    ctx.fillText(attributionText, xPos + padding, yPos + padding, textWidth)
  }

  return exportCanvas
}

const exportCanvasToBlob = (
  exportCanvas: HTMLCanvasElement,
  mimeType: string,
) => {
  return new Promise<Blob>((resolve, reject) => {
    exportCanvas.toBlob(
      (blob) => {
        if (blob) resolve(blob)
        else reject(new Error("Failed to export the map image"))
      },
      mimeType,
      IMAGE_QUALITY,
    )
  })
}

/** Calculate the offsets for trimming the exported image */
const getImageTrim = (
  map: MaplibreMap,
  width: number,
  height: number,
  mapBounds: LngLatBounds,
  filterBounds: LngLatBounds,
) => {
  if (!boundsIntersect(mapBounds, filterBounds)) {
    return { top: 0, left: 0, bottom: 0, right: 0 }
  }
  filterBounds = boundsIntersection(mapBounds, filterBounds)
  const bottomLeft = map.project(filterBounds.getSouthWest())
  const topRight = map.project(filterBounds.getNorthEast())
  const ratio = window.devicePixelRatio
  return {
    top: Math.ceil(topRight.y * ratio),
    left: Math.ceil(bottomLeft.x * ratio),
    bottom: Math.ceil(height - bottomLeft.y * ratio),
    right: Math.ceil(width - topRight.x * ratio),
  }
}
