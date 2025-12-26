import { decodeLonLat } from "@lib/polyline"
import type {
    RenderChangesetsData_Changeset,
    RenderElementsData,
    RenderNotesData,
} from "@lib/proto/shared_pb"
import type {
    Bounds,
    OSMChangeset,
    OSMNode,
    OSMNote,
    OSMObject,
    OSMWay,
} from "@lib/types"
import type { Feature, FeatureCollection } from "geojson"
import { NOTE_STATUS_MARKERS } from "./image"

interface RenderOptions {
    renderAreas: boolean // default: true
    featureIdCounter: number // default: 1
}

export const renderObjects = (
    objects: OSMObject[],
    options?: Partial<RenderOptions>,
): FeatureCollection => {
    const features: Feature[] = []
    let featureIdCounter = options?.featureIdCounter ?? 1

    const processChangeset = (changeset: OSMChangeset) => {
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

    const processNode = (node: OSMNode) => {
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
    const processWay = (way: OSMWay) => {
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

    const processNote = (note: OSMNote) => {
        features.push({
            type: "Feature",
            id: featureIdCounter++,
            properties: {
                type: "note",
                id: note.id?.toString() ?? "",
                icon: NOTE_STATUS_MARKERS[note.status],
                text: note.text,
            },
            geometry: {
                type: "Point",
                coordinates: note.geom,
            },
        })
    }

    for (const object of objects) {
        switch (object.type) {
            case "changeset":
                processChangeset(object)
                break
            case "node":
                processNode(object)
                break
            case "way":
                processWay(object)
                break
            case "note":
                processNote(object)
                break
            // Relations have no geometry to render
        }
    }

    return { type: "FeatureCollection", features }
}

export const convertRenderChangesetsData = (
    changesets: RenderChangesetsData_Changeset[],
) => {
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

export const convertRenderElementsData = (render: RenderElementsData | undefined) => {
    const result: (OSMNode | OSMWay)[] = []
    if (!render) return result
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

export const convertRenderNotesData = (render: RenderNotesData) => {
    const result: OSMNote[] = []
    for (const note of render.notes) {
        result.push({
            type: "note",
            id: note.id,
            geom: [note.lon, note.lat],
            status: note.status,
            text: note.text,
        })
    }
    return result
}
