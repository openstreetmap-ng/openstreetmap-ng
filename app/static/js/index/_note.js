import * as L from "leaflet"
import { configureStandardForm } from "../_standard-form.js"
import { getPageTitle } from "../_title.js"
import { focusMapObject } from "../leaflet/_focus-layer-util.js"
import { getBaseFetchController } from "./_base-fetch.js"

/**
 * Create a new note controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getNoteController = (map) => {
    const onLoaded = (sidebarContent) => {
        // Get elements
        const sidebarTitleElement = sidebarContent.querySelector(".sidebar-title")
        const sidebarTitle = sidebarTitleElement.textContent
        const locationButton = sidebarContent.querySelector(".location-btn")
        const commentForm = sidebarContent.querySelector("form.comment-form")
        const commentInput = commentForm.elements.text
        const eventInput = commentForm.elements.event
        const closeButton = commentForm.querySelector(".close-btn")
        const commentCloseButton = commentForm.querySelector(".comment-close-btn")
        const commentButton = commentForm.querySelector(".comment-btn")
        const submitButtons = commentForm.querySelectorAll("[type=submit]")

        // Set page title
        document.title = getPageTitle(sidebarTitle)

        // Handle not found
        if (!sidebarTitleElement.dataset.params) return

        // Get params
        const params = JSON.parse(sidebarTitleElement.dataset.params)
        const paramsId = params.id
        const lon = params.lon
        const lat = params.lat
        const open = params.open

        focusMapObject(map, {
            type: "note",
            id: paramsId,
            lon: lon,
            lat: lat,
            icon: open ? "open" : "closed",
        })

        // On location click, pan the map
        const onLocationClick = () => {
            const latLng = L.latLng(lat, lon)
            const currentZoom = map.getZoom()
            if (currentZoom < 16) {
                map.setView(latLng, 18)
            } else {
                map.panTo(latLng)
            }
        }

        // On success callback, reload the note and simulate map move (reload notes layer)
        const onFormSuccess = () => {
            map.panTo(map.getCenter(), { animate: false })
            base.unload()
            base.load({ id: paramsId })
        }

        // On comment input, update the button state
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

        // On submit click, set action input
        const onSubmitClick = (event) => {
            eventInput.value = event.target.dataset.event
        }

        // Listen for events
        locationButton.addEventListener("click", onLocationClick)
        if (commentForm) configureStandardForm(commentForm, onFormSuccess)
        if (commentInput) commentInput.addEventListener("input", onCommentInput)
        for (const button of submitButtons) button.addEventListener("click", onSubmitClick)

        // Initial update
        if (commentInput) onCommentInput()
    }

    const base = getBaseFetchController(map, "note", onLoaded)
    const baseLoad = base.load
    const baseUnload = base.unload

    base.load = ({ id }) => {
        const url = `/api/partial/note/${id}`
        baseLoad({ url })
    }

    base.unload = () => {
        focusMapObject(map, null)
        baseUnload()
    }

    return base
}
