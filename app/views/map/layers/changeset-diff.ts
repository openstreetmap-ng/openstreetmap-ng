import type { OSMNode, OSMWay } from "@utils/osm-objects"
import type { GeoJSONSource, Map as MaplibreMap } from "maplibre-gl"
import { renderObjects } from "../render-objects"
import {
  addMapLayer,
  emptyFeatureCollection,
  hasMapLayer,
  layersConfig,
  removeMapLayer,
  type LayerId,
} from "./layers"

export const CHANGESET_DIFF_BEFORE_LAYER_ID = "changeset-diff-before" as LayerId
export const CHANGESET_DIFF_AFTER_LAYER_ID = "changeset-diff-after" as LayerId

const DIFF_LAYER_TYPES = ["line", "circle"] as const
const BEFORE_COLOR = "#d84a4a"
const AFTER_COLOR = "#2b9b5f"

layersConfig.set(CHANGESET_DIFF_BEFORE_LAYER_ID, {
  specification: {
    type: "geojson",
    data: emptyFeatureCollection,
  },
  layerTypes: [...DIFF_LAYER_TYPES],
  layerOptions: {
    layout: {
      "line-cap": "round",
      "line-join": "round",
    },
    paint: {
      "line-color": BEFORE_COLOR,
      // Keep the before geometry visible beneath coincident after segments.
      "line-width": 7,
      "line-dasharray": [1, 1],
      "circle-radius": 9,
      "circle-color": "rgba(0, 0, 0, 0)",
      "circle-stroke-color": BEFORE_COLOR,
      "circle-stroke-width": 3,
    },
  },
  priority: 150,
})

layersConfig.set(CHANGESET_DIFF_AFTER_LAYER_ID, {
  specification: {
    type: "geojson",
    data: emptyFeatureCollection,
  },
  layerTypes: [...DIFF_LAYER_TYPES],
  layerOptions: {
    layout: {
      "line-cap": "round",
      "line-join": "round",
    },
    paint: {
      "line-color": AFTER_COLOR,
      "line-width": 4,
      "circle-radius": 5,
      "circle-color": AFTER_COLOR,
      "circle-opacity": 0.8,
      "circle-stroke-color": AFTER_COLOR,
      "circle-stroke-width": 1,
    },
  },
  priority: 151,
})

type DiffObjects = (OSMNode | OSMWay)[]

const ensureLayer = (map: MaplibreMap, layerId: LayerId) => {
  if (!hasMapLayer(map, layerId)) addMapLayer(map, layerId)
}

/** Replace the two map overlays used by changeset diff mode. */
export const setChangesetDiff = (
  map: MaplibreMap,
  before: DiffObjects,
  after: DiffObjects,
) => {
  ensureLayer(map, CHANGESET_DIFF_BEFORE_LAYER_ID)
  ensureLayer(map, CHANGESET_DIFF_AFTER_LAYER_ID)

  map
    .getSource<GeoJSONSource>(CHANGESET_DIFF_BEFORE_LAYER_ID)!
    .setData(renderObjects(before, { renderAreas: false }))
  map
    .getSource<GeoJSONSource>(CHANGESET_DIFF_AFTER_LAYER_ID)!
    .setData(renderObjects(after, { renderAreas: false }))
}

/** Clear and remove both changeset diff overlays from the map. */
export const clearChangesetDiff = (map: MaplibreMap) => {
  for (const layerId of [
    CHANGESET_DIFF_BEFORE_LAYER_ID,
    CHANGESET_DIFF_AFTER_LAYER_ID,
  ]) {
    map.getSource<GeoJSONSource>(layerId)?.setData(emptyFeatureCollection)
    if (hasMapLayer(map, layerId)) removeMapLayer(map, layerId)
  }
}
