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
        const commentForm = sidebarContent.querySelector("form")

        // Set page title
        document.title = getPageTitle(sidebarTitle)

        // Get params
        const params = JSON.parse(sidebarTitleElement.dataset.params)
        const paramsId = params.id
        const lon = params.lon
        const lat = params.lat
        const closedAt = params.closedAt
        const isOpen = closedAt === null

        focusMapObject(map, {
            type: "note",
            id: paramsId,
            lon: lon,
            lat: lat,
            icon: isOpen ? "open" : "closed",
            interactive: false,
        })

        // Focus on the note if it's offscreen
        const latLng = L.latLng(lat, lon)
        if (!map.getBounds().contains(latLng)) {
            map.panTo(latLng, { animate: false })
        }

        // On success callback, reload the note and simulate map move (reload notes layer)
        // TODO: test if reload notes layer works
        const onFormSuccess = () => {
            map.panTo(map.getCenter(), { animate: false })
            base.unload()
            base.load({ id: paramsId })
        }

        // Listen for events
        configureStandardForm(commentForm, onFormSuccess)
    }

    const base = getBaseFetchController("note", onLoaded)
    const baseLoad = base.load
    const baseUnload = base.unload

    base.load = ({ id }) => {
        const url = `/api/web/partial/note/${id}`
        baseLoad({ url })
    }

    base.unload = () => {
        focusMapObject(map, null)
        baseUnload()
    }

    return base
}
