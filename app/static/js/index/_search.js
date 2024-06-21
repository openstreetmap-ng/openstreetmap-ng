import i18next from "i18next"
import * as L from "leaflet"
import { qsEncode, qsParse } from "../_qs.js"
import { getPageTitle } from "../_title.js"
import { isLongitude } from "../_utils.js"
import { focusManyMapObjects, focusMapObject } from "../leaflet/_focus-layer.js"
import { getOverlayLayerById } from "../leaflet/_layers.js"
import { getMarkerIcon } from "../leaflet/_utils.js"
import { getBaseFetchController } from "./_base-fetch.js"
import { routerNavigateStrict } from "./_router.js"

const markerOpacity = 0.8

/**
 * Create a new search controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getSearchController = (map) => {
    const defaultTitle = i18next.t("site.search.search")
    const searchLayer = getOverlayLayerById("search")
    const searchInput = document.querySelector(".search-form").elements.q

    const onLoaded = (sidebarContent) => {
        const sidebar = sidebarContent.closest(".sidebar")
        const searchList = sidebarContent.querySelector(".search-list")

        // Handle no results
        if (!searchList) return

        const groupedElements = JSON.parse(searchList.dataset.leaflet)
        const results = searchList.querySelectorAll(".social-action")
        const layerGroup = L.layerGroup()

        for (let i = 0; i < results.length; i++) {
            const elements = groupedElements[i]
            const result = results[i]
            const dataset = result.dataset

            const lon = Number.parseFloat(dataset.lon)
            const lat = Number.parseFloat(dataset.lat)
            const marker = isLongitude(lon)
                ? L.marker(L.latLng(lat, lon), {
                      icon: getMarkerIcon("red", true),
                      opacity: markerOpacity,
                  })
                : null

            // On mouse enter, scroll result into view and focus elements
            const onMouseover = () => {
                const sidebarRect = sidebar.getBoundingClientRect()
                const resultRect = result.getBoundingClientRect()
                const isVisible = resultRect.top >= sidebarRect.top && resultRect.bottom <= sidebarRect.bottom
                if (!isVisible) result.scrollIntoView({ behavior: "smooth", block: "center" })

                result.classList.add("hover")
                focusManyMapObjects(map, elements, {
                    padBounds: 0.5,
                    maxZoom: 17,
                    intersects: true,
                    proportionCheck: false,
                })
                marker?.setOpacity(1)
            }

            // On mouse leave, unfocus elements
            const onMouseout = () => {
                result.classList.remove("hover")
                focusMapObject(map, null)
                marker?.setOpacity(markerOpacity)
            }

            // On marker click, navigate to the element
            const onMarkerClick = (e) => {
                const type = dataset.type
                const id = dataset.id
                const url = `/${type}/${id}`

                if (e.originalEvent.ctrlKey) {
                    window.open(url, "_blank")
                } else {
                    routerNavigateStrict(url)
                }
            }

            // Listen for events
            result.addEventListener("mouseover", onMouseover)
            result.addEventListener("mouseout", onMouseout)
            if (marker) {
                marker.addEventListener("mouseover", onMouseover)
                marker.addEventListener("mouseout", onMouseout)
                marker.addEventListener("click", onMarkerClick)
                layerGroup.addLayer(marker)
            }
        }

        searchLayer.clearLayers()
        if (results.length) searchLayer.addLayer(layerGroup)
        console.debug("Search showing", results.length, "results")
    }

    const base = getBaseFetchController(map, "search", onLoaded)
    const baseLoad = base.load
    const baseUnload = base.unload

    base.load = () => {
        // Create the search layer if it doesn't exist
        if (!map.hasLayer(searchLayer)) {
            console.debug("Adding overlay layer", searchLayer.options.layerId)
            map.addLayer(searchLayer)
            map.fire("overlayadd", { layer: searchLayer, name: searchLayer.options.layerId })
        }

        const searchParams = qsParse(location.search.substring(1))
        const query = searchParams.q || searchParams.query || ""

        // Set page title
        document.title = getPageTitle(query || defaultTitle)

        // Set search input if unset
        if (!searchInput.value) searchInput.value = query

        // Pad the bounds to gather more local results
        const bbox = map.getBounds().pad(1).toBBoxString()

        const url = `/api/partial/search?${qsEncode({ q: query, bbox })}`
        baseLoad({ url })
    }

    base.unload = () => {
        baseUnload()

        // Remove the search layer
        if (map.hasLayer(searchLayer)) {
            console.debug("Removing overlay layer", searchLayer.options.layerId)
            map.removeLayer(searchLayer)
            map.fire("overlayremove", { layer: searchLayer, name: searchLayer.options.layerId })
        }

        // Clear the search layer
        searchLayer.clearLayers()
    }

    return base
}
