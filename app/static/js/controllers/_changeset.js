import * as L from "leaflet"
import { configureStandardForm } from "../_standard-form.js"
import { getPageTitle } from "../_title.js"
import { focusMapObject } from "../leaflet/_map-focus.js"
import { getBaseFetchController } from "./_base_fetch.js"

/**
 * Create a new changeset controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getChangesetController = (map) => {
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
        const bounds = params.bounds

        // Not all changesets have a bounding box
        if (bounds !== null) {
            focusMapObject(map, {
                type: "changeset",
                id: paramsId,
                tags: new Map(), // currently unused
                bounds: bounds,
            })

            // Focus on the changeset if it's offscreen
            const latLngBounds = L.latLngBounds(bounds)
            if (!map.getBounds().contains(latLngBounds)) {
                map.fitBounds(latLngBounds, { animate: false })
            }
        }

        // On success callback, reload the changeset
        const onFormSuccess = () => {
            base.unload()
            base.load({ id: paramsId })
        }

        // Listen for events
        configureStandardForm(commentForm, onFormSuccess)
    }

    const base = getBaseFetchController("changeset", onLoaded)
    const baseLoad = base.load
    const baseUnload = base.unload

    base.load = ({ id }) => {
        const url = `/api/web/partial/changeset/${id}`
        baseLoad({ url })
    }

    base.unload = () => {
        focusMapObject(map, null)
        baseUnload()
    }

    return base
}
