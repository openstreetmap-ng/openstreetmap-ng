import type { Map as MaplibreMap, GeoJSONSource } from "maplibre-gl"
import type { Feature, FeatureCollection } from "geojson"
import {
    addMapLayer,
    emptyFeatureCollection,
    getExtendedLayerId,
    type LayerId,
    type LayerType,
    layersConfig,
} from "./layers"

export type DiffAction = "create" | "modify" | "delete"

export interface DiffNode {
    type: "node"
    id: string
    action: DiffAction
    lat: number
    lon: number
}

export interface DiffWay {
    type: "way"
    id: string
    action: DiffAction
    nodes: string[]
}

export type DiffElement = DiffNode | DiffWay

// Color scheme for diff actions
const DIFF_COLORS: Record<DiffAction, string> = {
    create: "#22c55e", // green
    modify: "#f97316", // orange
    delete: "#ef4444", // red
}

const LAYER_ID = "diff" as LayerId
const LAYER_TYPES: LayerType[] = ["fill", "line", "circle"]

// Register the diff layer configuration
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
            "circle-radius": 6,
            "circle-color": [
                "match",
                ["get", "action"],
                "create", DIFF_COLORS.create,
                "modify", DIFF_COLORS.modify,
                "delete", DIFF_COLORS.delete,
                "#888888", // fallback
            ],
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 2,
            "line-color": [
                "match",
                ["get", "action"],
                "create", DIFF_COLORS.create,
                "modify", DIFF_COLORS.modify,
                "delete", DIFF_COLORS.delete,
                "#888888",
            ],
            "line-width": 3,
            "line-opacity": 0.8,
            "fill-color": [
                "match",
                ["get", "action"],
                "create", DIFF_COLORS.create,
                "modify", DIFF_COLORS.modify,
                "delete", DIFF_COLORS.delete,
                "#888888",
            ],
            "fill-opacity": 0.2,
        },
    },
    priority: 150, // Higher than focus layer (140)
})

const layerAddedMap = new WeakSet<MaplibreMap>()

/**
 * Parse osmChange XML and extract all elements with their action types
 */
export const parseOsmChange = (xml: string): DiffElement[] => {
    const parser = new DOMParser()
    const doc = parser.parseFromString(xml, "text/xml")
    const elements: DiffElement[] = []

    for (const action of ["create", "modify", "delete"] as DiffAction[]) {
        const actionElement = doc.querySelector(action)
        if (!actionElement) continue

        // Parse nodes
        for (const nodeEl of actionElement.querySelectorAll("node")) {
            const id = nodeEl.getAttribute("id")
            const lat = nodeEl.getAttribute("lat")
            const lon = nodeEl.getAttribute("lon")
            if (id && lat && lon) {
                elements.push({
                    type: "node",
                    id,
                    action,
                    lat: Number.parseFloat(lat),
                    lon: Number.parseFloat(lon),
                })
            }
        }

        // Parse ways
        for (const wayEl of actionElement.querySelectorAll("way")) {
            const id = wayEl.getAttribute("id")
            if (!id) continue
            const nodes: string[] = []
            for (const ndEl of wayEl.querySelectorAll("nd")) {
                const ref = ndEl.getAttribute("ref")
                if (ref) nodes.push(ref)
            }
            if (nodes.length > 0) {
                elements.push({
                    type: "way",
                    id,
                    action,
                    nodes,
                })
            }
        }
    }

    return elements
}

/**
 * Convert diff elements to GeoJSON features
 */
export const renderDiffElements = (elements: DiffElement[]): FeatureCollection => {
    const features: Feature[] = []
    let featureIdCounter = 1

    // Build node coordinate lookup from all nodes in the changeset
    const nodeCoords = new Map<string, [number, number]>()
    for (const element of elements) {
        if (element.type === "node") {
            nodeCoords.set(element.id, [element.lon, element.lat])
        }
    }

    // Process all elements
    for (const element of elements) {
        if (element.type === "node") {
            features.push({
                type: "Feature",
                id: featureIdCounter++,
                properties: {
                    type: "node",
                    id: element.id,
                    action: element.action,
                },
                geometry: {
                    type: "Point",
                    coordinates: [element.lon, element.lat],
                },
            })
        } else if (element.type === "way") {
            // Resolve way coordinates from node refs
            const coords: [number, number][] = []
            for (const nodeId of element.nodes) {
                const coord = nodeCoords.get(nodeId)
                if (coord) {
                    coords.push(coord)
                }
            }

            if (coords.length >= 2) {
                // Check if it's a closed way (area)
                const isClosed =
                    coords.length >= 4 &&
                    coords[0][0] === coords[coords.length - 1][0] &&
                    coords[0][1] === coords[coords.length - 1][1]

                // Add line
                features.push({
                    type: "Feature",
                    id: featureIdCounter++,
                    properties: {
                        type: "way",
                        id: element.id,
                        action: element.action,
                    },
                    geometry: {
                        type: "LineString",
                        coordinates: coords,
                    },
                })

                // Add fill for closed ways
                if (isClosed) {
                    features.push({
                        type: "Feature",
                        id: featureIdCounter++,
                        properties: {
                            type: "way",
                            id: element.id,
                            action: element.action,
                        },
                        geometry: {
                            type: "Polygon",
                            coordinates: [coords],
                        },
                    })
                }
            }
        }
    }

    return { type: "FeatureCollection", features }
}

/**
 * Show diff visualization on the map
 * Pass empty elements array to hide the diff layer
 */
export const showDiff = (map: MaplibreMap, elements?: DiffElement[]) => {
    const source = map.getSource<GeoJSONSource>(LAYER_ID)!
    source.setData(emptyFeatureCollection)

    if (!elements?.length) return

    if (!layerAddedMap.has(map)) {
        layerAddedMap.add(map)
        addMapLayer(map, LAYER_ID)
    }

    const data = renderDiffElements(elements)
    source.setData(data)
    console.debug("DiffLayer: Rendered", data.features.length, "features")
}

/**
 * Hide the diff layer
 */
export const hideDiff = (map: MaplibreMap) => {
    const source = map.getSource<GeoJSONSource>(LAYER_ID)
    if (source) {
        source.setData(emptyFeatureCollection)
    }
}
