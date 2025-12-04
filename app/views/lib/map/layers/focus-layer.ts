import type { Geometry } from "geojson"
import {
    type GeoJSONSource,
    LngLatBounds,
    type LngLatLike,
    type Map as MaplibreMap,
} from "maplibre-gl"
import type { OSMObject } from "../../types"
import {
    checkLngLatBoundsIntersection,
    getLngLatBoundsSize,
    padLngLatBounds,
} from "../bounds"
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

export interface FocusOptions {
    /** Fit the map to the focused objects @default true */
    fitBounds?: boolean
    /** Amount of padding to add to the bounds @default 0.2 */
    padBounds?: number
    /** Maximum zoom level to focus on @default 18 */
    maxZoom?: number
    /** Whether to perform intersection check instead of containment @default false */
    intersects?: boolean
    /** Perform a proportion check when fitting the map @default true */
    proportionCheck?: boolean
}

const layerId = "focus" as LayerId
const layerTypes = Object.freeze(["fill", "line", "circle", "symbol"]) as LayerType[]
layersConfig.set(layerId as LayerId, {
    specification: {
        type: "geojson",
        data: emptyFeatureCollection,
    },
    layerTypes: layerTypes,
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

const lastPropertyMap = new WeakMap<MaplibreMap, [FocusLayerPaint, FocusLayerLayout]>()
const layerAddedMap = new WeakSet<MaplibreMap>()

/**
 * Focus many objects on the map and return their layers.
 * To unfocus, pass an empty array as the objects.
 */
export const focusObjects = (
    map: MaplibreMap,
    objects?: OSMObject[],
    paint?: FocusLayerPaint,
    layout?: FocusLayerLayout,
    options?: FocusOptions,
): void => {
    const source = map.getSource(layerId) as GeoJSONSource
    source.setData(emptyFeatureCollection)

    // If there are no objects to focus, remove the focus layer
    if (!objects?.length) return

    if (!layerAddedMap.has(map)) {
        layerAddedMap.add(map)
        addMapLayer(map, layerId)
    }

    const [lastPaint, lastLayout] = lastPropertyMap.get(map) ?? [undefined, undefined]

    for (const [last, current, setter] of [
        [lastPaint, paint, map.setPaintProperty],
        [lastLayout, layout, map.setLayoutProperty],
    ] as const) {
        if (last === current) continue

        for (const type of layerTypes) {
            const extendedLayerId = getExtendedLayerId(layerId, type)
            if (!map.getLayer(extendedLayerId)) continue

            const validPrefixes = [`${type}-`]
            if (type === "symbol") validPrefixes.push("icon-", "text-")

            if (last) {
                for (const k of Object.keys(last)) {
                    for (const prefix of validPrefixes) {
                        if (!k.startsWith(prefix) || (current && k in current)) continue
                        setter.call(map, extendedLayerId, k, null)
                        break
                    }
                }
            }
            if (current) {
                for (const [k, v] of Object.entries(current)) {
                    for (const prefix of validPrefixes) {
                        if (!k.startsWith(prefix)) continue
                        setter.call(map, extendedLayerId, k, v)
                        break
                    }
                }
            }
        }
    }

    lastPropertyMap.set(map, [paint, layout])

    const data = renderObjects(objects)
    source.setData(data)

    // Focus on the layers if they are offscreen
    if (options?.fitBounds ?? true) {
        let bounds: LngLatBounds | null = null
        for (const feature of data.features) {
            const geometryBounds = getGeometryBounds(feature.geometry)
            bounds = bounds ? bounds.extend(geometryBounds) : geometryBounds
        }
        const boundsPadded = padLngLatBounds(bounds, options?.padBounds ?? 0.2)
        const mapBounds = map.getBounds()

        const maxZoom = options?.maxZoom ?? 18
        const currentZoom = map.getZoom()
        const fitMaxZoom = Math.max(currentZoom, maxZoom)

        if (
            options?.intersects
                ? !checkLngLatBoundsIntersection(mapBounds, bounds)
                : !(
                      mapBounds.contains(bounds.getSouthWest()) &&
                      mapBounds.contains(bounds.getNorthEast())
                  )
        ) {
            console.debug(
                "Fitting map to",
                objects.length,
                "focus objects with zoom",
                fitMaxZoom,
                "(offscreen)",
            )
            map.fitBounds(boundsPadded, { maxZoom: fitMaxZoom, animate: false })
        } else if ((options?.proportionCheck ?? true) && fitMaxZoom > currentZoom) {
            const boundsSize = getLngLatBoundsSize(bounds)
            const mapBoundsSize = getLngLatBoundsSize(mapBounds)
            const proportion = boundsSize / mapBoundsSize
            if (proportion > 0 && proportion < 0.00035) {
                console.debug(
                    "Fitting map to",
                    objects.length,
                    "focus objects with zoom",
                    fitMaxZoom,
                    "(small)",
                )
                map.fitBounds(boundsPadded, { maxZoom: fitMaxZoom, animate: false })
            }
        }
    }
}

const getGeometryBounds = (g: Geometry): LngLatBounds => {
    if (g.type === "Point") {
        const [lon, lat] = g.coordinates
        return new LngLatBounds([lon, lat, lon, lat])
    }
    if (g.type === "LineString") {
        return g.coordinates //
            .reduce(
                (bounds, coord) => bounds.extend(coord as LngLatLike),
                new LngLatBounds(),
            )
    }
    if (g.type === "Polygon") {
        const outer = g.coordinates[0]
        return outer
            .slice(0, outer.length - 1)
            .reduce(
                (bounds, coord) => bounds.extend(coord as LngLatLike),
                new LngLatBounds(),
            )
    }
    if (g.type === "MultiPolygon") {
        let bounds = new LngLatBounds()
        for (const polygon of g.coordinates) {
            const outer = polygon[0]
            bounds = outer
                .slice(0, outer.length - 1)
                .reduce((bounds, coord) => bounds.extend(coord as LngLatLike), bounds)
        }
        return bounds
    }
    console.warn("Unsupported geometry type", g.type, "by getGeometryBounds")
    return new LngLatBounds()
}
