import type { Geometry } from "geojson"
import { type GeoJSONSource, LngLatBounds, type LngLatLike, type Map as MaplibreMap } from "maplibre-gl"
import type { OSMObject } from "../_types"
import {
    type AddMapLayerOptions,
    type LayerId,
    type LayerType,
    addMapLayer,
    emptyFeatureCollection,
    layersConfig,
    makeExtendedLayerId,
} from "./_layers"
import { renderObjects } from "./_render-objects"
import { getLngLatBoundsIntersection, getLngLatBoundsSize, padLngLatBounds } from "./_utils"

export type FocusLayerPaint = AddMapLayerOptions["paint"]

export interface FocusOptions {
    /** Fit the map to the focused objects */
    fitBounds?: boolean
    /** Amount of padding to add to the bounds */
    padBounds?: number
    /** Maximum zoom level to focus on */
    maxZoom?: number
    /** Whether to perform intersection check instead of containment */
    intersects?: boolean
    /** Perform a proportion check when fitting the map */
    proportionCheck?: boolean
}

const layerId = "focus" as LayerId
const layerTypes = Object.freeze(["fill", "line", "circle"]) as LayerType[]
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
    priority: 150,
})

let lastPaint: FocusLayerPaint | null = null
let layerAdded = false

// TODO: leaflet leftover
// note: {
//     pane: "focus",
// },
// noteHalo: {
//     radius: 20,
//     color: "#f60",
//     weight: 2.5,
//     opacity: 1,
//     fillOpacity: 0.5,
//     interactive: false,
// },
// export const focusStyles: RenderStyles = {
//     changeset: {
//         pane: "focus",
//         color: "#f90",
//         weight: 3,
//         opacity: 1,
//         fillColor: "#ffffaf",
//         fillOpacity: 0,
//         interactive: false,
//     },
//     element: {
//         pane: "focus",
//         color: "#f60",
//         weight: 4,
//         opacity: 1,
//         fillOpacity: 0.5,
//         interactive: false,
//     },
// }

/**
 * Focus many objects on the map and return their layers.
 * To unfocus, pass an empty array as the objects.
 */
export const focusObjects = (
    map: MaplibreMap,
    objects?: OSMObject[],
    paint?: FocusLayerPaint,
    options?: FocusOptions,
): void => {
    const source = map.getSource(layerId) as GeoJSONSource
    source.setData(emptyFeatureCollection)

    // If there are no objects to focus, remove the focus layer
    if (!objects?.length) return

    if (!layerAdded) {
        layerAdded = true
        addMapLayer(map, layerId)
    }

    if (paint && lastPaint !== paint) {
        lastPaint = paint
        for (const type of layerTypes) {
            const layer = map.getLayer(makeExtendedLayerId(layerId, type))
            if (!layer) continue

            // Apply only supported paint properties
            const validPrefixes = [`${type}-`]
            if (type === "symbol") validPrefixes.push("icon-", "text-")
            for (const [k, v] of Object.entries(paint)) {
                for (const prefix of validPrefixes) {
                    if (!k.startsWith(prefix)) continue
                    map.setPaintProperty(makeExtendedLayerId(layerId, type), k, v)
                }
            }
        }
    }

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
        const fitMaxZoom = maxZoom >= currentZoom ? maxZoom : map.getMaxZoom()

        if (
            options?.intersects
                ? getLngLatBoundsIntersection(mapBounds, bounds).isEmpty()
                : !(mapBounds.contains(bounds.getSouthWest()) && mapBounds.contains(bounds.getNorthEast()))
        ) {
            console.debug("Fitting map to", objects.length, "focus objects with zoom", fitMaxZoom, "(offscreen)")
            map.fitBounds(boundsPadded, { maxZoom: fitMaxZoom, animate: false })
        } else if ((options?.proportionCheck ?? true) && fitMaxZoom > currentZoom) {
            const boundsSize = getLngLatBoundsSize(bounds)
            const mapBoundsSize = getLngLatBoundsSize(mapBounds)
            const proportion = boundsSize / mapBoundsSize
            if (proportion > 0 && proportion < 0.00035) {
                console.debug("Fitting map to", objects.length, "focus objects with zoom", fitMaxZoom, "(small)")
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
            .reduce((bounds, coord) => bounds.extend(coord as LngLatLike), new LngLatBounds())
    }
    if (g.type === "Polygon") {
        const outer = g.coordinates[0]
        return outer
            .slice(0, outer.length - 1)
            .reduce((bounds, coord) => bounds.extend(coord as LngLatLike), new LngLatBounds())
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
