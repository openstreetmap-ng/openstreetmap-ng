import type { Map as MaplibreMap } from "maplibre-gl"

const mapHoverCounter = new WeakMap<MaplibreMap, number>()

/** Increment the map hover counter, and set the cursor to pointer */
export const incMapHover = (map: MaplibreMap): void => {
    const counter = mapHoverCounter.get(map)
    if (!counter) {
        mapHoverCounter.set(map, 1)
        map.getCanvas().style.cursor = "pointer"
    } else {
        mapHoverCounter.set(map, counter + 1)
    }
}

/** Decrement the map hover counter, and eventually reset the cursor */
export const decMapHover = (map: MaplibreMap): void => {
    const counter = mapHoverCounter.get(map)
    if (!counter) return
    if (counter === 1) {
        mapHoverCounter.set(map, 0)
        map.getCanvas().style.cursor = ""
    } else {
        mapHoverCounter.set(map, counter - 1)
    }
}
