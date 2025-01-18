import type { Geometry } from "geojson"
import { type GeoJSONSource, LngLatBounds, type LngLatLike, type Map as MaplibreMap } from "maplibre-gl"
import type { OSMObject } from "../_types"
import {
    addMapLayer,
    type AddMapLayerOptions,
    emptyFeatureCollection,
    type LayerId,
    layersConfig,
    makeExtendedLayerId,
    removeMapLayer,
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

export const focusLayerId = "focus" as LayerId
layersConfig.set(focusLayerId as LayerId, {
    specification: {
        type: "geojson",
        data: emptyFeatureCollection,
    },
    layerTypes: ["fill", "line", "circle"],
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

let enabled = false

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
 * Focus an object on the map and return its layer.
 * To unfocus, pass null as the object.
 */
export const focusMapObject = (
    map: MaplibreMap,
    object: OSMObject | null,
    paint: FocusLayerPaint,
    options?: FocusOptions,
): void => focusManyMapObjects(map, object ? [object] : [], paint, options)

/**
 * Focus many objects on the map and return their layers.
 * To unfocus, pass an empty array as the objects.
 */
export const focusManyMapObjects = (
    map: MaplibreMap,
    objects: OSMObject[],
    paint: FocusLayerPaint,
    options?: FocusOptions,
): void => {
    const source = map.getSource(focusLayerId) as GeoJSONSource

    // If there are no objects to focus, remove the focus layer
    if (!objects.length) {
        if (enabled) {
            enabled = false
            removeMapLayer(map, focusLayerId)
            source.setData(emptyFeatureCollection)
        }
        return
    }

    if (!enabled) {
        enabled = true
        addMapLayer(map, focusLayerId)
    }

    source.setData(emptyFeatureCollection)

    for (const type of ["fill", "line", "circle"]) {
        const layer = map.getLayer(makeExtendedLayerId(focusLayerId, type))
        for (const [k, v] of Object.entries(paint)) {
            layer.setPaintProperty(k, v)
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
        const boundsPadded = options?.padBounds ? padLngLatBounds(bounds, options.padBounds) : bounds
        const mapBounds = map.getBounds()

        const maxZoom = options?.maxZoom ?? 18
        const currentZoom = map.getZoom()
        const fitMaxZoom = maxZoom >= currentZoom ? maxZoom : null

        if (
            options?.intersects
                ? getLngLatBoundsIntersection(mapBounds, bounds).isEmpty()
                : !(mapBounds.contains(bounds.getSouthWest()) && mapBounds.contains(bounds.getNorthEast()))
        ) {
            console.debug("Fitting map to", objects.length, "focus objects with zoom", fitMaxZoom, "(offscreen)")
            map.fitBounds(boundsPadded, { maxZoom: fitMaxZoom, animate: false })
        } else if ((options?.proportionCheck ?? true) && fitMaxZoom > currentZoom) {
            const latLngSize = getLngLatBoundsSize(bounds)
            const mapBoundsSize = getLngLatBoundsSize(mapBounds)
            const proportion = latLngSize / mapBoundsSize
            if (proportion > 0 && proportion < 0.00035) {
                console.debug("Fitting map to", objects.length, "focus objects with zoom", fitMaxZoom, "(small)")
                map.fitBounds(boundsPadded, { maxZoom: fitMaxZoom, animate: false })
            }
        }
    }
}

const getGeometryBounds = (g: Geometry): LngLatBounds => {
    if (g.type === "Point") {
        return new LngLatBounds(g.coordinates as LngLatLike)
    }
    if (g.type === "LineString") {
        return g.coordinates
            .slice(1)
            .reduce(
                (bounds, coord) => bounds.extend(coord as LngLatLike),
                new LngLatBounds(g.coordinates[0] as LngLatLike),
            )
    }
    if (g.type === "Polygon") {
        const outer = g.coordinates[0]
        return outer
            .slice(1, outer.length - 1)
            .reduce((bounds, inner) => bounds.extend(inner as LngLatLike), new LngLatBounds(outer[0] as LngLatLike))
    }
    if (g.type === "MultiPolygon") {
        let bounds: LngLatBounds | null = null
        for (const polygon of g.coordinates) {
            const outer = polygon[0]
            const polygonBounds = outer
                .slice(1, outer.length - 1)
                .reduce((bounds, inner) => bounds.extend(inner as LngLatLike), new LngLatBounds(outer[0] as LngLatLike))
            bounds = bounds ? bounds.extend(polygonBounds) : polygonBounds
        }
        return bounds
    }
    console.warn("Unsupported geometry type", g.type, "by getGeometryBounds")
    return new LngLatBounds()
}
