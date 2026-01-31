import { polylineDecode } from "@lib/polyline"
import type { GetMapChangesetsResponse_ChangesetValid } from "@lib/proto/changeset_pb"
import type { RenderElementsDataValid } from "@lib/proto/element_pb"
import type { GetMapNotesResponseValid } from "@lib/proto/note_pb"
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
  let {
    featureIdCounter = 1,
    renderAreas = true, //
  } = options ?? {}
  const features: Feature[] = []

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
        body: note.body,
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
  changesets: GetMapChangesetsResponse_ChangesetValid[],
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

export const convertRenderElementsData = (
  render: RenderElementsDataValid | undefined,
) => {
  const result: (OSMNode | OSMWay)[] = []
  if (!render) return result
  for (const way of render.ways) {
    result.push({
      type: "way",
      id: way.id,
      geom: polylineDecode(way.line, 6),
      area: way.isArea,
    })
  }
  for (const node of render.nodes) {
    result.push({
      type: "node",
      id: node.id,
      geom: [node.location.lon, node.location.lat],
    })
  }
  return result
}

export const convertRenderNotesData = (render: GetMapNotesResponseValid) => {
  const result: OSMNote[] = []
  for (const note of render.notes) {
    result.push({
      type: "note",
      id: note.id,
      geom: [note.location.lon, note.location.lat],
      status: note.status,
      body: note.body,
    })
  }
  return result
}
