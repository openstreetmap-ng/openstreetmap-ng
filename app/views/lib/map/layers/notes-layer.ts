import { NoteRoute } from "@index/note"
import { routerNavigate } from "@index/router"
import { NOTE_QUERY_AREA_MAX_SIZE } from "@lib/config"
import { createKeyedAbort } from "@lib/keyed-abort"
import { NoteService } from "@lib/proto/note_pb"
import { rpcClient } from "@lib/rpc"
import { delay } from "@std/async/delay"
import { SECOND } from "@std/datetime/constants"
import {
  type GeoJSONSource,
  type LngLatBounds,
  type Map as MaplibreMap,
  Popup,
} from "maplibre-gl"
import { boundsIntersection, boundsSize, boundsToString } from "../bounds"
import { clearMapHover, setMapHover } from "../hover"
import { loadMapImage } from "../image"
import { convertRenderNotesData, renderObjects } from "../render-objects"
import {
  addLayerEventHandler,
  emptyFeatureCollection,
  layersConfig,
  NOTES_LAYER_CODE,
  NOTES_LAYER_ID,
} from "./layers"

const LAYER_ID = NOTES_LAYER_ID
const LAYER_CODE = NOTES_LAYER_CODE
layersConfig.set(LAYER_ID, {
  specification: {
    type: "geojson",
    data: emptyFeatureCollection,
  },
  layerCode: LAYER_CODE,
  layerTypes: ["symbol"],
  layerOptions: {
    layout: {
      "icon-image": ["get", "icon"],
      "icon-allow-overlap": true,
      "icon-size": 41 / 128,
      "icon-padding": 0,
      "icon-anchor": "bottom",
    },
    paint: {
      "icon-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 1, 0.8],
    },
  },
  priority: 130,
})

const RELOAD_PROPORTION_THRESHOLD = 0.9

const abort = createKeyedAbort()
export const notesLayerPending = abort.pending

/** Configure the notes layer for the given map */
export const configureNotesLayer = (map: MaplibreMap) => {
  const source = map.getSource<GeoJSONSource>(LAYER_ID)!
  let enabled = false
  let fetchedBounds: LngLatBounds | null = null

  // On feature click, navigate to the note
  map.on("click", LAYER_ID, (e) => {
    const noteId = e.features![0].properties.id
    routerNavigate(NoteRoute, { id: BigInt(noteId) })
  })

  let hoveredFeatureId: number | null = null
  let hoverPopupAbort: AbortController | undefined
  const hoverPopup: Popup = new Popup({ closeButton: false, closeOnMove: true })

  const clearHoverState = () => {
    if (hoveredFeatureId) {
      map.removeFeatureState({ source: LAYER_ID, id: hoveredFeatureId })
      hoveredFeatureId = null
    }
    hoverPopupAbort?.abort()
    hoverPopup.remove()
    clearMapHover(map, LAYER_ID)
  }

  const clearNotes = () => {
    clearHoverState()
    source.setData(emptyFeatureCollection)
    fetchedBounds = null
  }

  map.on("mousemove", LAYER_ID, async (e) => {
    const lngLat = e.lngLat
    const feature = e.features![0]
    const featureId = feature.id as number
    if (hoveredFeatureId === featureId) return
    if (hoveredFeatureId) {
      map.removeFeatureState({ source: LAYER_ID, id: hoveredFeatureId })
    } else {
      setMapHover(map, LAYER_ID)
    }
    hoveredFeatureId = featureId
    map.setFeatureState({ source: LAYER_ID, id: hoveredFeatureId }, { hover: true })
    // Show popup after a short delay
    hoverPopupAbort?.abort()
    hoverPopupAbort = new AbortController()
    hoverPopup.remove()
    try {
      await delay(0.5 * SECOND, { signal: hoverPopupAbort.signal })
    } catch {
      return
    }
    console.debug("NotesLayer: Showing popup", feature.properties.id)
    hoverPopup.setText(feature.properties.body).setLngLat(lngLat).addTo(map)
  })
  map.on("mouseleave", LAYER_ID, clearHoverState)

  /** On map update, fetch the notes and update the notes layer */
  const updateLayer = async () => {
    // Skip if the notes layer is not visible
    if (!enabled) return

    // Skip updates if the area is too big
    const fetchBounds = map.getBounds()
    const fetchArea = boundsSize(fetchBounds)
    if (fetchArea > NOTE_QUERY_AREA_MAX_SIZE) {
      abort.abort()
      clearNotes()
      return
    }

    // Skip updates if the view is satisfied
    if (fetchedBounds) {
      const visibleBounds = boundsIntersection(fetchedBounds, fetchBounds)
      const visibleArea = boundsSize(visibleBounds)
      const proportion = visibleArea / Math.max(boundsSize(fetchedBounds), fetchArea)
      if (proportion > RELOAD_PROPORTION_THRESHOLD) return
    }

    const token = abort.start(boundsToString(fetchBounds))
    if (!token) return

    const [[minLon, minLat], [maxLon, maxLat]] = fetchBounds
      .adjustAntiMeridian()
      .toArray()

    try {
      const render = await rpcClient(NoteService).getMapNotes(
        {
          bbox: { minLon, minLat, maxLon, maxLat },
        },
        {
          signal: token.signal,
        },
      )

      const notes = convertRenderNotesData(render)
      source.setData(renderObjects(notes))
      fetchedBounds = fetchBounds
      console.debug("NotesLayer: Loaded", notes.length, "notes")
    } catch (error) {
      if (token.signal.aborted) return
      console.error("NotesLayer: Failed to fetch", error)
      clearNotes()
    } finally {
      token.done()
    }
  }
  map.on("moveend", updateLayer)
  map.on("reloadnoteslayer", () => {
    console.debug("NotesLayer: Reloading")
    fetchedBounds = null
    abort.abort()
    updateLayer()
  })

  addLayerEventHandler((isAdded, eventLayerId) => {
    if (eventLayerId !== LAYER_ID) return
    enabled = isAdded
    if (isAdded) {
      // Load image resources
      loadMapImage(map, "marker-open")
      loadMapImage(map, "marker-closed")
      loadMapImage(map, "marker-hidden")
      updateLayer()
    } else {
      abort.abort()
      clearNotes()
    }
  })
}
