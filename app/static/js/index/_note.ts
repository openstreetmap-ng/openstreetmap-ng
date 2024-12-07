import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import * as L from "leaflet"
import { configureStandardForm } from "../_standard-form"
import { configureStandardPagination } from "../_standard-pagination"
import { getPageTitle } from "../_title"
import { focusMapObject } from "../leaflet/_focus-layer"
import { PartialNoteParamsSchema } from "../proto/shared_pb"
import { getBaseFetchController } from "./_base-fetch"
import type { IndexController } from "./_router"

/** Create a new note controller */
export const getNoteController = (map: L.Map): IndexController => {
    const base = getBaseFetchController(map, "note", (sidebarContent) => {
        // Get elements
        const sidebarTitleElement = sidebarContent.querySelector(".sidebar-title") as HTMLElement
        const sidebarTitle = sidebarTitleElement.textContent

        // Set page title
        document.title = getPageTitle(sidebarTitle)

        // Handle not found
        if (!sidebarTitleElement.dataset.params) return

        // Get params
        const params = fromBinary(PartialNoteParamsSchema, base64Decode(sidebarTitleElement.dataset.params))

        focusMapObject(map, {
            type: "note",
            id: params.id,
            geom: [params.lat, params.lon],
            icon: params.open ? "open" : "closed",
        })

        // On location click, pan the map
        const locationButton = sidebarContent.querySelector("button.location-btn")
        locationButton.addEventListener("click", () => {
            const latLng = L.latLng(params.lat, params.lon)
            const currentZoom = map.getZoom()
            if (currentZoom < 16) {
                map.setView(latLng, 18)
            } else {
                map.panTo(latLng)
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
                map.panTo(map.getCenter(), { animate: false })
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
            base.load({ url })
        },
        unload: () => {
            focusMapObject(map, null)
            base.unload()
        },
    }
    return controller
}
