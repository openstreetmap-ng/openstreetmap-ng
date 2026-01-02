import type { Map as MaplibreMap } from "maplibre-gl"

const mapHoverState = new WeakMap<MaplibreMap, Set<string>>()

/** Indicate that the map is hovered over the given layer/id */
export const setMapHover = (map: MaplibreMap, id: string) => {
  let counter = mapHoverState.get(map)
  if (counter === undefined) {
    counter = new Set<string>()
    mapHoverState.set(map, counter)
  }
  if (!counter.size) map.getCanvas().style.cursor = "pointer"
  counter.add(id)
}

/** Indicate that the map is no longer hovered over the given layer/id */
export const clearMapHover = (map: MaplibreMap, id: string) => {
  const counter = mapHoverState.get(map)
  if (!counter) return
  counter.delete(id)
  if (!counter.size) map.getCanvas().style.cursor = ""
}
