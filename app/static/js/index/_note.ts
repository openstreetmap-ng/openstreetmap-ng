import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import { type Map as MaplibreMap, Marker } from "maplibre-gl"
import { configureStandardForm } from "../_standard-form"
import { configureStandardPagination } from "../_standard-pagination"
import { setPageTitle } from "../_title"
import { type FocusLayerPaint, focusObjects } from "../leaflet/_focus-layer"
import { getMarkerIconElement, markerIconAnchor } from "../leaflet/_utils.ts"
import { PartialNoteParamsSchema } from "../proto/shared_pb"
import { getBaseFetchController } from "./_base-fetch"
import type { IndexController } from "./_router"

const themeColor = "#f60"
const focusPaintHalo: FocusLayerPaint = {
    "circle-radius": 20,
    "circle-color": themeColor,
    "circle-opacity": 0.5,
    "circle-stroke-width": 2.5,
    "circle-stroke-color": themeColor,
}

/** Create a new note controller */
export const getNoteController = (map: MaplibreMap): IndexController => {
    let marker: Marker | null = null

    const base = getBaseFetchController(map, "note", (sidebarContent) => {
        const sidebarTitleElement = sidebarContent.querySelector(".sidebar-title") as HTMLElement
        setPageTitle(sidebarTitleElement.textContent)

        // Handle not found
        if (!sidebarTitleElement.dataset.params) return

        // Get params
        const params = fromBinary(PartialNoteParamsSchema, base64Decode(sidebarTitleElement.dataset.params))
        const center: [number, number] = [params.lon, params.lat]

        marker = new Marker({
            anchor: markerIconAnchor,
            element: getMarkerIconElement(params.open ? "open" : "closed", false),
        })
            .setLngLat(center)
            .addTo(map)

        focusObjects(
            map,
            [
                {
                    type: "note",
                    id: null,
                    geom: center,
                    open: true,
                    text: "",
                },
            ],
            focusPaintHalo,
            { fitBounds: false },
        )

        // On location click, pan the map
        const locationButton = sidebarContent.querySelector("button.location-btn")
        locationButton.addEventListener("click", () => {
            const currentZoom = map.getZoom()
            if (currentZoom < 16) {
                map.flyTo({ center, zoom: 18 })
            } else {
                map.panTo(center)
            }
        })

        const commentsPagination = sidebarContent.querySelector("div.note-comments-pagination")
        if (commentsPagination) configureStandardPagination(commentsPagination)

        const commentForm = sidebarContent.querySelector("form.comment-form")
        if (commentForm) {
            const commentInput = commentForm.elements.namedItem("text") as HTMLInputElement
            const eventInput = commentForm.elements.namedItem("event") as HTMLInputElement
            const closeButton = commentForm.querySelector("button.close-btn")
            const commentCloseButton = commentForm.querySelector("button.comment-close-btn")
            const commentButton = commentForm.querySelector("button.comment-btn")
            const submitButtons = commentForm.querySelectorAll("button[type=submit]")

            /** On success callback, reload the note and simulate map move (reload notes layer) */
            const onFormSuccess = () => {
                map.panBy([0, 0], { animate: false })
                controller.unload()
                controller.load({ id: params.id.toString() })
            }
            const subscriptionForm = sidebarContent.querySelector("form.subscription-form")
            configureStandardForm(subscriptionForm, onFormSuccess)
            configureStandardForm(commentForm, onFormSuccess)

            /** On submit click, set event type */
            const onSubmitClick = ({ target }: MouseEvent) => {
                eventInput.value = (target as HTMLButtonElement).dataset.event
            }
            for (const button of submitButtons) button.addEventListener("click", onSubmitClick)

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
            const url = `/api/partial/note/${id}`
            base.load(url)
        },
        unload: () => {
            focusObjects(map)
            marker.remove()
            marker = null
            base.unload()
        },
    }
    return controller
}
