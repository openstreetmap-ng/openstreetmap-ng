import * as L from "leaflet"
import { getPageTitle } from "../_title.js"
import { focusManyMapObjects, focusMapObject, focusStyles } from "../leaflet/_focus-layer-util.js"
import { getBaseFetchController } from "./_base-fetch.js"

// TODO: always show close button, even when loading
// TODO: ensure no empty changesets are returned
// TODO: load more button

const minBoundsSizePx = 20

/**
 * Create a new changesets history controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getChangesetsHistoryController = (map) => {
    let loaded = false

    // Make bounds minimum size to make them easier to click
    const makeBoundsMinimumSize = (bounds) => {
        const [minLon, minLat, maxLon, maxLat] = bounds
        const mapBottomLeft = map.project(L.latLng(minLat, minLon))
        const mapTopRight = map.project(L.latLng(maxLat, maxLon))
        const width = mapTopRight.x - mapBottomLeft.x
        const height = mapBottomLeft.y - mapTopRight.y

        if (width < minBoundsSizePx) {
            const diff = minBoundsSizePx - width
            mapBottomLeft.x -= diff / 2
            mapTopRight.x += diff / 2
        }

        if (height < minBoundsSizePx) {
            const diff = minBoundsSizePx - height
            mapBottomLeft.y += diff / 2
            mapTopRight.y -= diff / 2
        }

        const latLngBottomLeft = map.unproject(mapBottomLeft)
        const latLngTopRight = map.unproject(mapTopRight)
        return [latLngBottomLeft.lng, latLngBottomLeft.lat, latLngTopRight.lng, latLngTopRight.lat]
    }

    // Configure result actions to handle focus and clicks
    const configureResultActions = (container) => {
        const resultActions = container.querySelectorAll(".result-action")
        const changesets = Array.from(resultActions).map((resultAction) => {
            const params = JSON.parse(resultAction.dataset.params)
            const bounds = makeBoundsMinimumSize(params.bounds)
            const boudsArea = (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])
            return {
                type: "changeset",
                id: params.id,
                bounds: bounds,
                boudsArea,
                resultAction, // dirty!
            }
        })

        // Sort by bounds area (descending)
        changesets.sort((a, b) => b.boudsArea - a.boudsArea)

        /**
         * @type {L.Rectangle[]}
         */
        const layers = focusManyMapObjects(map, changesets)

        for (let i = 0; i < changesets.length; i++) {
            const changeset = changesets[i]
            const resultAction = changeset.resultAction
            const layer = layers[i]

            // On hover, focus on the element
            const onMouseEnter = () => {
                const style = focusStyles.changeset
                resultAction.classList.add("hover")
                layer.setStyle({
                    color: "#FF6600",
                    weight: style.weight * 1.5,
                    fillOpacity: Math.min(style.fillOpacity + 0.3, 1),
                })
            }

            // On hover end, unfocus the element
            const onMouseLeave = () => {
                const style = focusStyles.changeset
                resultAction.classList.remove("hover")
                layer.setStyle({
                    color: style.color,
                    weight: style.weight,
                    fillOpacity: style.fillOpacity,
                })
            }

            // On layer click, click the result action
            const onLayerClick = () => {
                resultAction.click()
            }

            // Listen for events
            resultAction.addEventListener("mouseenter", onMouseEnter)
            resultAction.addEventListener("mouseleave", onMouseLeave)
            layer.addEventListener("mouseover", onMouseEnter)
            layer.addEventListener("mouseout", onMouseLeave)
            layer.addEventListener("click", onLayerClick)
        }
    }

    const onLoaded = (sidebarContent) => {
        // Get elements
        const sidebarTitleElement = sidebarContent.querySelector(".sidebar-title")
        const sidebarTitle = sidebarTitleElement.textContent

        // Set page title
        document.title = getPageTitle(sidebarTitle)

        configureResultActions(sidebarContent)
    }

    const base = getBaseFetchController(map, "changesets-history", onLoaded)
    const baseLoad = base.load
    const baseUnload = base.unload
    let lastLoadOptions

    base.load = ({ scope, displayName }) => {
        let url

        if (scope === "nearby") {
            url = "/api/web/partial/changeset/history/nearby_users"
        } else if (scope === "friends") {
            url = "/api/web/partial/changeset/history/friends"
        } else if (displayName) {
            url = `/api/web/partial/changeset/history/user/${displayName}`
        } else {
            url = "/api/web/partial/changeset/history"
        }

        lastLoadOptions = { scope, displayName }
        baseLoad({ url })

        loaded = true
    }

    base.unload = () => {
        focusMapObject(map, null)
        baseUnload()

        loaded = false
    }

    /**
     * On map update, reload the changesets history
     * @returns {void}
     */
    const onMapZoomOrMoveEnd = () => {
        // Skip updates if the sidebar is hidden
        if (!loaded) return

        console.debug("Reloading changesets history")
        base.unload()
        base.load(lastLoadOptions)
    }

    // Listen for events
    map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)

    return base
}
