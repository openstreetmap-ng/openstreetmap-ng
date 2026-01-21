import type { OSMObject } from "@lib/types"
import { assertExists } from "@std/assert"
import { filterKeys } from "@std/collections/filter-keys"
import type { Geometry } from "geojson"
import {
  type GeoJSONSource,
  LngLatBounds,
  type LngLatLike,
  type Map as MaplibreMap,
} from "maplibre-gl"
import { type FitBoundsOptions, fitBoundsIfNeeded } from "../bounds"
import { renderObjects } from "../render-objects"
import {
  type AddMapLayerOptions,
  addMapLayer,
  emptyFeatureCollection,
  getExtendedLayerId,
  type LayerId,
  type LayerType,
  layersConfig,
} from "./layers"

export type FocusLayerPaint = AddMapLayerOptions["paint"]
export type FocusLayerLayout = AddMapLayerOptions["layout"]

const LAYER_ID = "focus" as LayerId
const LAYER_TYPES: LayerType[] = ["fill", "line", "circle", "symbol"]
layersConfig.set(LAYER_ID, {
  specification: {
    type: "geojson",
    data: emptyFeatureCollection,
  },
  layerTypes: LAYER_TYPES,
  layerOptions: {
    layout: {
      "line-cap": "round",
      "line-join": "round",
    },
    paint: {
      "circle-radius": 10,
    },
  },
  priority: 140,
})

const lastPropertyMap = new WeakMap<
  MaplibreMap,
  [FocusLayerPaint | null | undefined, FocusLayerLayout | null | undefined]
>()
const layerAddedMap = new WeakSet<MaplibreMap>()

/**
 * Focus many objects on the map and return their layers.
 * To unfocus, pass an empty array as the objects.
 */
export const focusObjects = (
  map: MaplibreMap,
  objects?: OSMObject[],
  paint?: FocusLayerPaint | null,
  layout?: FocusLayerLayout | null,
  fitOpts?: FitBoundsOptions | false,
) => {
  const source = map.getSource<GeoJSONSource>(LAYER_ID)!

  // If there are no objects to focus, remove the focus layer
  if (!objects?.length) {
    source.setData(emptyFeatureCollection)
    return
  }

  if (!layerAddedMap.has(map)) {
    layerAddedMap.add(map)
    addMapLayer(map, LAYER_ID)
  }

  const [lastPaint, lastLayout] = lastPropertyMap.get(map) ?? [undefined, undefined]

  for (const [last, current, setter] of [
    [lastPaint, paint, map.setPaintProperty],
    [lastLayout, layout, map.setLayoutProperty],
  ] as const) {
    if (last === current) continue

    for (const type of LAYER_TYPES) {
      const extendedLayerId = getExtendedLayerId(LAYER_ID, type)
      if (!map.getLayer(extendedLayerId)) continue

      const validPrefixes = [`${type}-`]
      if (type === "symbol") validPrefixes.push("icon-", "text-")

      const hasValidPrefix = (key: string) =>
        validPrefixes.some((prefix) => key.startsWith(prefix))

      if (last) {
        const filteredLast = filterKeys(last as Record<string, unknown>, hasValidPrefix)
        for (const k of Object.keys(filteredLast)) {
          if (!(current && k in current)) setter.call(map, extendedLayerId, k, null)
        }
      }
      if (current) {
        const filteredCurrent = filterKeys(
          current as Record<string, unknown>,
          hasValidPrefix,
        )
        for (const [k, v] of Object.entries(filteredCurrent))
          setter.call(map, extendedLayerId, k, v)
      }
    }
  }

  lastPropertyMap.set(map, [paint, layout])

  const data = renderObjects(objects)
  source.setData(data)

  if (fitOpts === false) return

  // Focus on the layers if they are offscreen
  let bounds: LngLatBounds | undefined
  for (const feature of data.features) {
    const geometryBounds = getGeometryBounds(feature.geometry)
    bounds = bounds ? bounds.extend(geometryBounds) : geometryBounds
  }
  assertExists(bounds)
  const result = fitBoundsIfNeeded(map, bounds, fitOpts)
  if (result) {
    console.debug(
      `FocusLayer: Fitting bounds (${result.reason})`,
      objects.length,
      "objects, zoom",
      result.fitMaxZoom,
    )
  }
}

const getGeometryBounds = (g: Geometry) => {
  if (g.type === "Point") {
    const [lon, lat] = g.coordinates
    return new LngLatBounds([lon, lat, lon, lat])
  }
  if (g.type === "LineString") {
    return g.coordinates //
      .reduce((bounds, coord) => bounds.extend(coord as LngLatLike), new LngLatBounds())
  }
  if (g.type === "Polygon") {
    const outer = g.coordinates[0]
    return outer
      .slice(0, -1)
      .reduce((bounds, coord) => bounds.extend(coord as LngLatLike), new LngLatBounds())
  }
  if (g.type === "MultiPolygon") {
    let bounds = new LngLatBounds()
    for (const polygon of g.coordinates) {
      const outer = polygon[0]
      bounds = outer
        .slice(0, -1)
        .reduce((bounds, coord) => bounds.extend(coord as LngLatLike), bounds)
    }
    return bounds
  }
  console.warn("FocusLayer: Unsupported geometry type", g.type)
  return new LngLatBounds()
}
