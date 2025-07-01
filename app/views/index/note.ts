import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import type { GeoJSONSource, Map as MaplibreMap } from "maplibre-gl"
import {
    loadMapImage,
    markerClosedImageUrl,
    markerHiddenImageUrl,
    markerOpenImageUrl,
} from "../lib/map/image.ts"
import {
    addMapLayer,
    emptyFeatureCollection,
    type LayerId,
    layersConfig,
    removeMapLayer,
} from "../lib/map/layers/layers.ts"
import { renderObjects } from "../lib/map/render-objects"
import { PartialNoteParamsSchema } from "../lib/proto/shared_pb"
import { configureStandardForm } from "../lib/standard-form"
import { configureStandardPagination } from "../lib/standard-pagination"
import { setPageTitle } from "../lib/title"
import { getBaseFetchController } from "./_base-fetch"
import type { IndexController } from "./_router"

const themeColor = "#f60"
const layerId = "note" as LayerId
layersConfig.set(layerId as LayerId, {
    specification: {
        type: "geojson",
        data: emptyFeatureCollection,
    },
    layerTypes: ["circle", "symbol"],
    layerOptions: {
        layout: {
            "icon-image": ["concat", "marker-", ["get", "status"]],
            "icon-size": 41 / 128,
            "icon-padding": 0,
            "icon-anchor": "bottom",
        },
        paint: {
            "circle-radius": 20,
            "circle-color": themeColor,
            "circle-opacity": 0.5,
            "circle-stroke-width": 2.5,
            "circle-stroke-color": themeColor,
        },
    },
    priority: 135,
})

/** Create a new note controller */
export const getNoteController = (map: MaplibreMap): IndexController => {
    const source = map.getSource(layerId) as GeoJSONSource

    const base = getBaseFetchController(map, "note", (sidebarContent) => {
        const sidebarTitleElement = sidebarContent.querySelector(
            ".sidebar-title",
        ) as HTMLElement
        setPageTitle(sidebarTitleElement.textContent)

        // Handle not found
        if (!sidebarTitleElement.dataset.params) return

        // Get params
        const params = fromBinary(
            PartialNoteParamsSchema,
            base64Decode(sidebarTitleElement.dataset.params),
        )
        const center: [number, number] = [params.lon, params.lat]

        // Display marker layer
        switch (params.status) {
            case "open":
                loadMapImage(map, "marker-open", markerOpenImageUrl)
                break
            case "closed":
                loadMapImage(map, "marker-closed", markerClosedImageUrl)
                break
            case "hidden":
                loadMapImage(map, "marker-hidden", markerHiddenImageUrl)
                break
            default:
                console.error("Unsupported note status", params.status)
                break
        }

        const data = renderObjects([
            {
                type: "note",
                geom: center,
                status: params.status as "open" | "closed" | "hidden",
                text: "",
            },
        ])
        source.setData(data)
        addMapLayer(map, layerId)

        // On location click, pan the map
        const locationButton = sidebarContent.querySelector("button.location-btn")
        locationButton.addEventListener("click", () => {
            console.debug("onLocationButtonClick", center)
            map.flyTo({ center, zoom: Math.max(map.getZoom(), 15) })
        })

        configureStandardPagination(
            sidebarContent.querySelector("div.note-comments-pagination"),
        )

        const commentForm = sidebarContent.querySelector("form.comment-form")
        if (commentForm) {
            const commentInput = commentForm.elements.namedItem(
                "text",
            ) as HTMLInputElement
            const eventInput = commentForm.elements.namedItem(
                "event",
            ) as HTMLInputElement
            const closeButton = commentForm.querySelector("button.close-btn")
            const commentCloseButton = commentForm.querySelector(
                "button.comment-close-btn",
            )
            const commentButton = commentForm.querySelector("button.comment-btn")
            const submitButtons = commentForm.querySelectorAll("button[type=submit]")

            /** On success callback, reload the note details and the notes layer */
            const onFormSuccess = () => {
                map.fire("reloadnoteslayer")
                controller.unload()
                controller.load({ id: params.id.toString() })
            }
            const subscriptionForm = sidebarContent.querySelector(
                "form.subscription-form",
            )
            configureStandardForm(subscriptionForm, onFormSuccess)
            configureStandardForm(commentForm, onFormSuccess)

            /** On submit click, set event type */
            const onSubmitClick = ({ target }: MouseEvent) => {
                eventInput.value = (target as HTMLButtonElement).dataset.event
            }
            for (const button of submitButtons)
                button.addEventListener("click", onSubmitClick)

            if (commentInput) {
                /** On comment input, update the button state */
                const onCommentInput = () => {
                    const hasValue = commentInput.value.trim().length > 0
                    if (hasValue) {
                        closeButton.classList.add("d-none")
                        commentCloseButton.classList.remove("d-none")
                        commentButton.disabled = false
                    } else {
                        closeButton.classList.remove("d-none")
                        commentCloseButton.classList.add("d-none")
                        commentButton.disabled = true
                    }
                }

                commentInput.addEventListener("input", onCommentInput)

                // Initial update
                onCommentInput()
            }
        }
    })

    const controller: IndexController = {
        load: ({ id }) => {
            const url = `/partial/note/${id}`
            base.load(url)
        },
        unload: () => {
            removeMapLayer(map, layerId)
            source.setData(emptyFeatureCollection)
            base.unload()
        },
    }
    return controller
}
