import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import { getBaseFetchController } from "@index/_base-fetch"
import { loadMapImage, NOTE_STATUS_MARKERS, type NoteStatus } from "@lib/map/image.ts"
import {
    type FocusLayerLayout,
    type FocusLayerPaint,
    focusObjects,
} from "@lib/map/layers/focus-layer.ts"
import { PartialNoteParamsSchema } from "@lib/proto/shared_pb"
import { configureReportButtonsLazy } from "@lib/report-modal"
import { configureStandardForm } from "@lib/standard-form"
import { configureStandardPagination } from "@lib/standard-pagination"
import { setPageTitle } from "@lib/title"
import type { Map as MaplibreMap } from "maplibre-gl"
import type { IndexController } from "./router"

const THEME_COLOR = "#f60"
const focusPaint: FocusLayerPaint = {
    "circle-radius": 20,
    "circle-color": THEME_COLOR,
    "circle-opacity": 0.5,
    "circle-stroke-width": 2.5,
    "circle-stroke-color": THEME_COLOR,
}
const focusLayout: FocusLayerLayout = {
    "icon-image": ["get", "icon"],
    "icon-size": 41 / 128,
    "icon-padding": 0,
    "icon-anchor": "bottom",
}

export const getNoteController = (map: MaplibreMap) => {
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
        const status = params.status as NoteStatus
        loadMapImage(map, NOTE_STATUS_MARKERS[status])

        focusObjects(
            map,
            [
                {
                    type: "note",
                    geom: center,
                    status,
                    text: "",
                },
            ],
            focusPaint,
            focusLayout,
            { padBounds: 0, maxZoom: 15, proportionCheck: false },
        )

        // On location click, pan the map
        const locationButton = sidebarContent.querySelector(
            ".location-container button",
        )
        locationButton.addEventListener("click", () => {
            console.debug("onLocationButtonClick", center)
            map.flyTo({ center, zoom: Math.max(map.getZoom(), 15) })
        })

        // Configure report buttons
        configureReportButtonsLazy(sidebarContent)

        const disposePagination = configureStandardPagination(
            sidebarContent.querySelector("div.note-comments-pagination"),
        )

        const commentForm = sidebarContent.querySelector("form.comment-form")
        if (commentForm) {
            const commentInput = commentForm.querySelector("textarea[name=text]")
            const eventInput = commentForm.querySelector("input[name=event]")
            const closeButton = commentForm.querySelector("button.close-btn")
            const commentCloseButton = commentForm.querySelector(
                "button.comment-close-btn",
            )
            const commentButton = commentForm.querySelector("button.comment-btn")
            const submitButtons = commentForm.querySelectorAll("button[type=submit]")

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

            const onSubmitClick = ({ target }: MouseEvent) => {
                eventInput.value = (target as HTMLButtonElement).dataset.event
            }
            for (const button of submitButtons)
                button.addEventListener("click", onSubmitClick)

            if (commentInput) {
                const onCommentInput = () => {
                    const hasValue = commentInput.value.trim().length > 0
                    closeButton.classList.toggle("d-none", hasValue)
                    commentCloseButton.classList.toggle("d-none", !hasValue)
                    commentButton.disabled = !hasValue
                }

                commentInput.addEventListener("input", onCommentInput)

                // Initial update
                onCommentInput()
            }
        }

        return () => {
            disposePagination()
            focusObjects(map)
        }
    })

    const controller: IndexController = {
        load: ({ id }) => {
            base.load(`/partial/note/${id}`)
        },
        unload: base.unload,
    }
    return controller
}
