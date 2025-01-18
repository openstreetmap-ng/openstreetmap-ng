import { fromBinary } from "@bufbuild/protobuf"
import type { GeoJSONSource, Map as MaplibreMap } from "maplibre-gl"
import { noteQueryAreaMaxSize } from "../_config"
import { routerNavigateStrict } from "../index/_router"
import { RenderNotesDataSchema } from "../proto/shared_pb"
import {
    addLayerEventHandler,
    emptyFeatureCollection,
    hasMapLayer,
    type LayerCode,
    type LayerId,
    layersConfig,
} from "./_layers"
import { convertRenderNotesData, renderObjects } from "./_render-objects.ts"
import { getLngLatBoundsSize } from "./_utils"

const layerId = "notes" as LayerId
layersConfig.set(layerId as LayerId, {
    specification: {
        type: "geojson",
        data: emptyFeatureCollection,
    },
    layerCode: "N" as LayerCode,
    layerTypes: ["symbol"],
    defaultLayerOptions: {
        [layerId]: {
            layout: {
                "icon-image": ["case", ["boolean", ["get", "open"], false], "note-open", "note-closed"],
                "icon-allow-overlap": true,
                "icon-padding": 0,
                "icon-anchor": "bottom",
            },
            paint: {
                "icon-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 1, 0.8],
            },
        },
    },
    priority: 130,
})

const openImageUrl = "/static/img/marker/open.webp"
const closedImageUrl = "/static/img/marker/closed.webp"

/** Configure the notes layer for the given map */
export const configureNotesLayer = (map: MaplibreMap): void => {
    const source = map.getSource(layerId) as GeoJSONSource
    let enabled = hasMapLayer(map, layerId)
    let abortController: AbortController | null = null

    // Load image resources
    map.loadImage(openImageUrl).then((resp) => map.addImage("note-open", resp.data))
    map.loadImage(closedImageUrl).then((resp) => map.addImage("note-closed", resp.data))

    // On marker click, navigate to the note
    map.on("click", layerId, (e) => {
        const noteId = e.features[0].properties.id
        routerNavigateStrict(`/note/${noteId}`)
    })

    // TODO: leaflet leftover, tooltips
    // const tooltip = new maplibregl.Popup({
    //   closeButton: false,
    //   closeOnClick: false
    // });
    //
    // map.on('mouseenter', 'points-layer', (e) => {
    //   if (e.features.length > 0) {
    //     const coordinates = e.features[0].geometry.coordinates.slice();
    //     const description = e.features[0].properties.description;
    //
    //     // Set a timeout to show the tooltip after 1 second (1000 milliseconds)
    //     hoverTimeout = setTimeout(() => {
    //       tooltip
    //         .setLngLat(coordinates)
    //         .setHTML(description)
    //         .addTo(map);
    //     }, 1000);
    //   }
    // });
    //
    // map.on('mouseleave', 'points-layer', () => {
    //   // Clear the timeout if the mouse leaves before the tooltip is shown
    //   clearTimeout(hoverTimeout);
    //   tooltip.remove();
    // });

    // TODO: reduce updates, zoom, bounds

    /** On map update, fetch the notes and update the notes layer */
    const updateLayer = (): void => {
        // Skip if the notes layer is not visible
        if (!enabled) return

        // Abort any pending request
        abortController?.abort()
        abortController = new AbortController()

        // Skip updates if the area is too big
        const bounds = map.getBounds()
        const area = getLngLatBoundsSize(bounds)
        if (area > noteQueryAreaMaxSize) return

        const minLon = bounds.getWest()
        const minLat = bounds.getSouth()
        const maxLon = bounds.getEast()
        const maxLat = bounds.getNorth()

        fetch(`/api/web/note/map?bbox=${minLon},${minLat},${maxLon},${maxLat}`, {
            method: "GET",
            mode: "same-origin",
            cache: "no-store", // request params are too volatile to cache
            signal: abortController.signal,
            priority: "high",
        })
            .then(async (resp) => {
                if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)

                const buffer = await resp.arrayBuffer()
                const render = fromBinary(RenderNotesDataSchema, new Uint8Array(buffer))
                const notes = convertRenderNotesData(render)
                source.setData(renderObjects(notes))
                console.debug("Notes layer showing", notes.length, "notes")
            })
            .catch((error) => {
                if (error.name === "AbortError") return
                console.error("Failed to fetch notes", error)
                source.setData(emptyFeatureCollection)
            })
    }
    map.on("moveend", updateLayer)

    addLayerEventHandler((isAdded, eventLayerId) => {
        if (eventLayerId !== layerId) return
        enabled = isAdded
        if (isAdded) {
            updateLayer()
        } else {
            abortController?.abort()
            abortController = null
            source.setData(emptyFeatureCollection)
        }
    })
}
