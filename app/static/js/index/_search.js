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
    const searchForm = document.querySelector(".search-form")
    const searchInput = searchForm.elements.q

    const onLoaded = (sidebarContent) => {
        const sidebar = sidebarContent.closest(".sidebar")
        const searchList = sidebarContent.querySelector(".search-list")

        // Handle no results
        if (!searchList) return

        const dataset = searchList.dataset
        const boundsStr = dataset.bounds
        const globalSearch = !boundsStr
        const groupedElements = JSON.parse(dataset.leaflet)
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
                    // Focus on hover only during global search
                    fitBounds: globalSearch,
                    padBounds: 0.5,
                    maxZoom: globalSearch ? 14 : 17,
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

        if (!globalSearch) {
            const bounds = boundsStr.split(",").map(Number.parseFloat)
            map.flyToBounds(L.latLngBounds(L.latLng(bounds[1], bounds[0]), L.latLng(bounds[3], bounds[2])))
            console.debug("Search focusing on", boundsStr)
        }
    }

    const base = getBaseFetchController(map, "search", onLoaded)
    const baseLoad = base.load
    const baseUnload = base.unload

    base.load = () => {
        // Stick the search form
        searchForm.classList.add("sticky-top")

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

        // Load empty sidebar to ensure proper bbox
        baseLoad({ url: null })
        // Pad the bounds to avoid floating point errors
        const bbox = map.getBounds().pad(-0.01).toBBoxString()
        const url = `/api/partial/search?${qsEncode({ q: query, bbox })}`
        baseLoad({ url })
    }

    base.unload = () => {
        baseUnload()

        // Clear the search layer
        searchLayer.clearLayers()

        // Remove the search layer
        if (map.hasLayer(searchLayer)) {
            console.debug("Removing overlay layer", searchLayer.options.layerId)
            map.removeLayer(searchLayer)
            map.fire("overlayremove", { layer: searchLayer, name: searchLayer.options.layerId })
        }

        // Unstick the search form
        searchForm.classList.remove("sticky-top")
    }

    return base
}
