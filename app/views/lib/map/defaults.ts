import type { Map as MaplibreMap } from "maplibre-gl"

export const configureDefaultMapBehavior = (map: MaplibreMap): void => {
    map.setProjection({ type: "mercator" })

    map.dragRotate.disable()
    map.keyboard.disableRotation()
    map.touchZoomRotate.disableRotation()

    // Use constant zoom rate for consistent behavior
    // https://github.com/maplibre/maplibre-gl-js/issues/5367
    const zoomRate = 1 / 300
    map.scrollZoom.setWheelZoomRate(zoomRate)
    map.scrollZoom.setZoomRate(zoomRate)
}
