import { fromBinary } from "@bufbuild/protobuf"
import { routerNavigateStrict } from "@index/router"
import { toggleLayerSpinner } from "@index/sidebar/layers"
import { NOTE_QUERY_AREA_MAX_SIZE } from "@lib/config"
import { RenderNotesDataSchema } from "@lib/proto/shared_pb"
import { assert } from "@std/assert"
import { delay } from "@std/async/delay"
import { SECOND } from "@std/datetime/constants"
import {
    type GeoJSONSource,
    type LngLatBounds,
    type Map as MaplibreMap,
    Popup,
} from "maplibre-gl"
import { getLngLatBoundsIntersection, getLngLatBoundsSize } from "../bounds"
import { clearMapHover, setMapHover } from "../hover"
import { loadMapImage } from "../image"
import { convertRenderNotesData, renderObjects } from "../render-objects"
import {
    addLayerEventHandler,
    emptyFeatureCollection,
    type LayerCode,
    type LayerId,
    layersConfig,
} from "./layers"

const LAYER_ID = "notes" as LayerId
layersConfig.set(LAYER_ID, {
    specification: {
        type: "geojson",
        data: emptyFeatureCollection,
    },
    layerCode: "N" as LayerCode,
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
            "icon-opacity": [
                "case",
                ["boolean", ["feature-state", "hover"], false],
                1,
                0.8,
            ],
        },
    },
    priority: 130,
})

const RELOAD_PROPORTION_THRESHOLD = 0.9

/** Configure the notes layer for the given map */
export const configureNotesLayer = (map: MaplibreMap) => {
    const source = map.getSource<GeoJSONSource>(LAYER_ID)!
    let enabled = false
    let fetchedBounds: LngLatBounds | null = null
    let abortController: AbortController | undefined

    // On feature click, navigate to the note
    map.on("click", LAYER_ID, (e) => {
        const noteId = e.features![0].properties.id
        routerNavigateStrict(`/note/${noteId}`)
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
        hoverPopup.setText(feature.properties.text).setLngLat(lngLat).addTo(map)
    })
    map.on("mouseleave", LAYER_ID, () => {
        if (!hoveredFeatureId) return
        clearHoverState()
    })

    /** On map update, fetch the notes and update the notes layer */
    const updateLayer = async () => {
        // Skip if the notes layer is not visible
        if (!enabled) return

        // Abort any pending request
        abortController?.abort()
        abortController = new AbortController()

        // Skip updates if the area is too big
        const fetchBounds = map.getBounds()
        const fetchArea = getLngLatBoundsSize(fetchBounds)
        if (fetchArea > NOTE_QUERY_AREA_MAX_SIZE) return

        // Skip updates if the view is satisfied
        if (fetchedBounds) {
            const visibleBounds = getLngLatBoundsIntersection(
                fetchedBounds,
                fetchBounds,
            )
            const visibleArea = getLngLatBoundsSize(visibleBounds)
            const proportion =
                visibleArea / Math.max(getLngLatBoundsSize(fetchedBounds), fetchArea)
            if (proportion > RELOAD_PROPORTION_THRESHOLD) return
        }

        const [[minLon, minLat], [maxLon, maxLat]] = fetchBounds
            .adjustAntiMeridian()
            .toArray()

        toggleLayerSpinner(LAYER_ID, true)
        try {
            const resp = await fetch(
                `/api/web/note/map?bbox=${minLon},${minLat},${maxLon},${maxLat}`,
                {
                    signal: abortController.signal,
                    priority: "high",
                },
            )
            assert(resp.ok, `${resp.status} ${resp.statusText}`)

            const buffer = await resp.arrayBuffer()
            const render = fromBinary(RenderNotesDataSchema, new Uint8Array(buffer))
            const notes = convertRenderNotesData(render)
            source.setData(renderObjects(notes))
            fetchedBounds = fetchBounds
            console.debug("NotesLayer: Loaded", notes.length, "notes")
        } catch (error) {
            if (error.name === "AbortError") return
            console.error("NotesLayer: Failed to fetch", error)
            source.setData(emptyFeatureCollection)
        } finally {
            toggleLayerSpinner(LAYER_ID, false)
        }
    }
    map.on("moveend", updateLayer)
    map.on("reloadnoteslayer", () => {
        console.debug("NotesLayer: Reloading")
        fetchedBounds = null
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
            clearHoverState()
            abortController?.abort()
            toggleLayerSpinner(LAYER_ID, false)
            source.setData(emptyFeatureCollection)
            fetchedBounds = null
        }
    })
}
