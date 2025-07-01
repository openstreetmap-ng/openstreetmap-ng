import type { Feature, FeatureCollection } from "geojson"
import { decodeLonLat } from "../polyline"
import type {
    RenderChangesetsData_Changeset,
    RenderElementsData,
    RenderNotesData,
} from "../proto/shared_pb"
import type {
    Bounds,
    OSMChangeset,
    OSMNode,
    OSMNote,
    OSMObject,
    OSMWay,
} from "../types"

interface RenderOptions {
    /** Whether to render areas */
    renderAreas: boolean
}

/** Render OSMObjects to GeoJSON data */
export const renderObjects = (
    objects: OSMObject[],
    options?: Partial<RenderOptions>,
): FeatureCollection => {
    const features: Feature[] = []
    let featureIdCounter = 1

    const processChangeset = (changeset: OSMChangeset): void => {
        const properties = {
            type: "changeset",
            id: changeset.id.toString(),
            firstFeatureId: featureIdCounter,
            numBounds: changeset.bounds.length,
        }
        for (const [minLon, minLat, maxLon, maxLat] of changeset.bounds) {
            const boundsArea = (maxLon - minLon) * (maxLat - minLat)
            const boundsProperties = { ...properties, boundsArea }
            const outer = [
                [minLon, minLat],
                [minLon, maxLat],
                [maxLon, maxLat],
                [maxLon, minLat],
                [minLon, minLat],
            ]
            features.push({
                type: "Feature",
                id: featureIdCounter++,
                properties: boundsProperties,
                geometry: {
                    type: "LineString",
                    coordinates: outer,
                },
            })
            features.push({
                type: "Feature",
                id: featureIdCounter++,
                properties: boundsProperties,
                geometry: {
                    type: "Polygon",
                    coordinates: [outer],
                },
            })
        }
    }

    const processNode = (node: OSMNode): void => {
        features.push({
            type: "Feature",
            id: featureIdCounter++,
            properties: {
                type: "node",
                id: node.id.toString(),
            },
            geometry: {
                type: "Point",
                coordinates: node.geom,
            },
        })
    }

    const renderAreas = options?.renderAreas ?? true
    const processWay = (way: OSMWay): void => {
        const properties = {
            type: "way",
            id: way.id.toString(),
        }
        features.push({
            type: "Feature",
            id: featureIdCounter++,
            properties,
            geometry: {
                type: "LineString",
                coordinates: way.geom,
            },
        })
        if (renderAreas && way.area) {
            features.push({
                type: "Feature",
                id: featureIdCounter++,
                properties,
                geometry: {
                    type: "Polygon",
                    coordinates: [way.geom],
                },
            })
        }
    }

    const processNote = (note: OSMNote): void => {
        features.push({
            type: "Feature",
            id: featureIdCounter++,
            properties: {
                type: "note",
                id: note.id?.toString(),
                status: note.status,
                text: note.text,
            },
            geometry: {
                type: "Point",
                coordinates: note.geom,
            },
        })
    }

    const processFnMap = {
        changeset: processChangeset,
        node: processNode,
        way: processWay,
        note: processNote,
    }

    for (const object of objects) {
        // @ts-ignore
        const fn = processFnMap[object.type]
        if (fn) fn(object)
        else console.error("Unsupported feature type", object)
    }

    return { type: "FeatureCollection", features }
}

/** Convert render data to OSMChangesets */
export const convertRenderChangesetsData = (
    changesets: RenderChangesetsData_Changeset[],
): OSMChangeset[] => {
    const result: OSMChangeset[] = []
    for (const changeset of changesets) {
        const bounds: Bounds[] = []
        for (const { minLon, minLat, maxLon, maxLat } of changeset.bounds) {
            bounds.push([minLon, minLat, maxLon, maxLat])
        }
        result.push({
            type: "changeset",
            id: changeset.id,
            bounds: bounds,
        })
    }
    return result
}

/** Convert render data to OSMObjects */
export const convertRenderElementsData = (
    render: RenderElementsData,
): (OSMNode | OSMWay)[] => {
    const result: (OSMNode | OSMWay)[] = []
    for (const way of render.ways) {
        result.push({
            type: "way",
            id: way.id,
            geom: decodeLonLat(way.line, 6),
            area: way.area,
        })
    }
    for (const node of render.nodes) {
        result.push({
            type: "node",
            id: node.id,
            geom: [node.lon, node.lat],
        })
    }
    return result
}

/** Convert render notes data to OSMNotes */
export const convertRenderNotesData = (render: RenderNotesData): OSMNote[] => {
    const result: OSMNote[] = []
    for (const note of render.notes) {
        result.push({
            type: "note",
            id: note.id,
            geom: [note.lon, note.lat],
            status: note.status as "open" | "closed" | "hidden",
            text: note.text,
        })
    }
    return result
}
