import { fromBinary } from "@bufbuild/protobuf"
import {
    type GeoJSONSource,
    type LngLat,
    type LngLatBounds,
    type Map as MaplibreMap,
    Popup,
} from "maplibre-gl"
import { routerNavigateStrict } from "../../../index/router"
import { toggleLayerSpinner } from "../../../index/sidebar/layers"
import { config } from "../../config"
import { RenderNotesDataSchema } from "../../proto/shared_pb"
import { getLngLatBoundsIntersection, getLngLatBoundsSize } from "../bounds"
import { clearMapHover, setMapHover } from "../hover"
import {
    loadMapImage,
    markerClosedImageUrl,
    markerHiddenImageUrl,
    markerOpenImageUrl,
} from "../image"
import { convertRenderNotesData, renderObjects } from "../render-objects"
import {
    addLayerEventHandler,
    emptyFeatureCollection,
    type LayerCode,
    type LayerId,
    layersConfig,
} from "./layers"

const layerId = "notes" as LayerId
layersConfig.set(layerId as LayerId, {
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

const reloadProportionThreshold = 0.9

/** Configure the notes layer for the given map */
export const configureNotesLayer = (map: MaplibreMap): void => {
    const source = map.getSource(layerId) as GeoJSONSource
    let enabled = false
    let fetchedBounds: LngLatBounds | null = null
    let abortController: AbortController | null = null

    // On feature click, navigate to the note
    map.on("click", layerId, (e) => {
        const noteId = e.features[0].properties.id
        routerNavigateStrict(`/note/${noteId}`)
    })

    let hoveredFeatureId: number | null = null
    let hoverLngLat: LngLat | null = null
    let hoverPopupTimeout: ReturnType<typeof setTimeout> | null = null
    const hoverPopup: Popup = new Popup({ closeButton: false, closeOnMove: true })

    map.on("mousemove", layerId, (e) => {
        hoverLngLat = e.lngLat
        const feature = e.features[0]
        const featureId = feature.id as number
        if (hoveredFeatureId) {
            if (hoveredFeatureId === featureId) return
            map.removeFeatureState({ source: layerId, id: hoveredFeatureId })
        } else {
            setMapHover(map, layerId)
        }
        hoveredFeatureId = featureId
        map.setFeatureState({ source: layerId, id: hoveredFeatureId }, { hover: true })
        // Show popup after a short delay
        clearTimeout(hoverPopupTimeout)
        hoverPopup.remove()
        hoverPopupTimeout = setTimeout(() => {
            console.debug(
                "Showing popup for note",
                feature.properties.id,
                "at",
                hoverLngLat,
            )
            hoverPopup
                .setText(feature.properties.text)
                .setLngLat(hoverLngLat)
                .addTo(map)
        }, 500)
    })
    map.on("mouseleave", layerId, () => {
        map.removeFeatureState({ source: layerId, id: hoveredFeatureId })
        hoveredFeatureId = null
        clearTimeout(hoverPopupTimeout)
        hoverPopup.remove()
        clearMapHover(map, layerId)
    })

    /** On map update, fetch the notes and update the notes layer */
    const updateLayer = (): void => {
        // Skip if the notes layer is not visible
        if (!enabled) return

        // Abort any pending request
        abortController?.abort()
        abortController = new AbortController()

        // Skip updates if the area is too big
        const fetchBounds = map.getBounds()
        const fetchArea = getLngLatBoundsSize(fetchBounds)
        if (fetchArea > config.noteQueryAreaMaxSize) return

        // Skip updates if the view is satisfied
        if (fetchedBounds) {
            const visibleBounds = getLngLatBoundsIntersection(
                fetchedBounds,
                fetchBounds,
            )
            const visibleArea = getLngLatBoundsSize(visibleBounds)
            const proportion =
                visibleArea / Math.max(getLngLatBoundsSize(fetchedBounds), fetchArea)
            if (proportion > reloadProportionThreshold) return
        }

        const [[minLon, minLat], [maxLon, maxLat]] = fetchBounds
            .adjustAntiMeridian()
            .toArray()

        toggleLayerSpinner(layerId, true)
        fetch(`/api/web/note/map?bbox=${minLon},${minLat},${maxLon},${maxLat}`, {
            signal: abortController.signal,
            priority: "high",
        })
            .then(async (resp) => {
                toggleLayerSpinner(layerId, false)
                if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)

                const buffer = await resp.arrayBuffer()
                const render = fromBinary(RenderNotesDataSchema, new Uint8Array(buffer))
                const notes = convertRenderNotesData(render)
                source.setData(renderObjects(notes))
                fetchedBounds = fetchBounds
                console.debug("Notes layer showing", notes.length, "notes")
            })
            .catch((error) => {
                if (error.name === "AbortError") return
                console.error("Failed to fetch notes", error)
                toggleLayerSpinner(layerId, false)
                source.setData(emptyFeatureCollection)
            })
    }
    map.on("moveend", updateLayer)
    map.on("reloadnoteslayer", () => {
        console.debug("Reloading notes layer")
        fetchedBounds = null
        updateLayer()
    })

    addLayerEventHandler((isAdded, eventLayerId) => {
        if (eventLayerId !== layerId) return
        enabled = isAdded
        if (isAdded) {
            // Load image resources
            loadMapImage(map, "marker-open", markerOpenImageUrl)
            loadMapImage(map, "marker-closed", markerClosedImageUrl)
            loadMapImage(map, "marker-hidden", markerHiddenImageUrl)
            updateLayer()
        } else {
            abortController?.abort()
            abortController = null
            toggleLayerSpinner(layerId, false)
            source.setData(emptyFeatureCollection)
            clearMapHover(map, layerId)
            fetchedBounds = null
        }
    })
}
