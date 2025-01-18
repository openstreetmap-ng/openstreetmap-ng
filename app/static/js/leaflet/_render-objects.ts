import { decode } from "@mapbox/polyline"
import type { Feature, FeatureCollection, Position } from "geojson"
import type { OSMChangeset, OSMNode, OSMNote, OSMObject, OSMWay } from "../_types"
import type { RenderElementsData, RenderNotesData } from "../proto/shared_pb"

interface RenderOptions {
    /** Whether to render areas */
    renderAreas: boolean
}

/** Render OSMObjects to GeoJSON data */
export const renderObjects = (objects: OSMObject[], options?: Partial<RenderOptions>): FeatureCollection => {
    const features: Feature[] = []

    const processChangeset = (changeset: OSMChangeset): void => {
        const coordinates: Position[][][] = []
        for (const [minLon, minLat, maxLon, maxLat] of changeset.bounds ?? []) {
            coordinates.push([
                [
                    [minLon, minLat],
                    [minLon, maxLat],
                    [maxLon, maxLat],
                    [maxLon, minLat],
                    [minLon, minLat],
                ],
            ])
        }
        features.push({
            type: "Feature",
            properties: {
                type: changeset.type,
                id: changeset.id,
            },
            geometry: {
                type: "MultiPolygon",
                coordinates,
            },
        })
    }

    const processNode = (node: OSMNode): void => {
        features.push({
            type: "Feature",
            properties: {
                type: node.type,
                id: node.id,
                version: node.version,
            },
            geometry: {
                type: "Point",
                coordinates: node.geom,
            },
        })
    }

    const renderAreas = options?.renderAreas ?? true
    const processWay = (way: OSMWay): void => {
        features.push({
            type: "Feature",
            properties: {
                type: way.type,
                id: way.id,
                version: way.version,
            },
            geometry:
                renderAreas && way.area
                    ? {
                          type: "Polygon",
                          coordinates: [way.geom],
                      }
                    : {
                          type: "LineString",
                          coordinates: way.geom,
                      },
        })
    }

    const processNote = (note: OSMNote): void => {
        features.push({
            type: "Feature",
            properties: {
                type: note.type,
                id: note.id,
                open: note.open,
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

    console.debug("Rendered", features.length, "features")
    return { type: "FeatureCollection", features }
}

/** Convert render data to OSMObjects */
export const convertRenderElementsData = (render: RenderElementsData): (OSMNode | OSMWay)[] => {
    const result: (OSMNode | OSMWay)[] = []
    for (const way of render.ways) {
        result.push({
            type: "way",
            id: way.id,
            geom: decode(way.line, 6),
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
            open: note.open,
            text: note.text,
        })
    }
    return result
}
