import type { Map as MaplibreMap } from "maplibre-gl"

export const configureDefaultMapBehavior = (map: MaplibreMap) => {
  map.setProjection({ type: "mercator" })

  map.dragRotate.disable()
  map.keyboard.disableRotation()
  map.touchZoomRotate.disableRotation()

  // Use constant zoom rate for consistent behavior
  // https://github.com/maplibre/maplibre-gl-js/issues/5367
  const ZOOM_RATE = 1 / 300
  map.scrollZoom.setWheelZoomRate(ZOOM_RATE)
  map.scrollZoom.setZoomRate(ZOOM_RATE)
}
