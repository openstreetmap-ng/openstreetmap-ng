import i18next from "i18next"
import * as L from "leaflet"
import { qsEncode, qsParse } from "../_qs.js"
import { getPageTitle } from "../_title.js"
import { isLongitude } from "../_utils.js"
import { focusManyMapObjects, focusMapObject } from "../leaflet/_focus-layer.js"
import { getOverlayLayerById } from "../leaflet/_layers.js"
import { getLatLngBoundsIntersection, getLatLngBoundsSize, getMarkerIcon } from "../leaflet/_utils.js"
import { getBaseFetchController } from "./_base-fetch.js"
import { routerNavigateStrict } from "./_router.js"
import { setSearchFormQuery } from "./_search-form.js"

const markerOpacity = 0.8
const searchAlertChangeThreshold = 0.9
const focusOptions = {
    padBounds: 0.5,
    maxZoom: 14,
    intersects: true,
    proportionCheck: false,
}

/**
 * Create a new search controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getSearchController = (map) => {
    const defaultTitle = i18next.t("site.search.search")
    const searchLayer = getOverlayLayerById("search")
    const searchForm = document.querySelector(".search-form")
    const searchAlert = document.querySelector(".search-alert")
    let initialBounds = null

    // On search alert click, reload the search with the new area
    const onSearchAlertClick = () => {
        console.debug("Searching within new area")
        base.unload()
        base.load({ local_only: true })
    }

    // On map update, check if view was changed and show alert if so
    const onMapZoomOrMoveEnd = () => {
        if (!initialBounds) {
            initialBounds = map.getBounds()
            console.debug("Search initial bounds set to", initialBounds)
            return
        }

        if (!searchAlert.classList.contains("d-none")) return

        const mapBounds = map.getBounds()
        const intersectionBounds = getLatLngBoundsIntersection(initialBounds, mapBounds)
        const intersectionBoundsSize = getLatLngBoundsSize(intersectionBounds)

        const mapBoundsSize = getLatLngBoundsSize(mapBounds)
        const initialBoundsSize = getLatLngBoundsSize(initialBounds)
        const proportion = Math.min(intersectionBoundsSize / mapBoundsSize, intersectionBoundsSize / initialBoundsSize)
        if (proportion > searchAlertChangeThreshold) return

        searchAlert.classList.remove("d-none")
        map.removeEventListener("zoomend moveend", onMapZoomOrMoveEnd)
    }

    const onLoaded = (sidebarContent) => {
        const sidebar = sidebarContent.closest(".sidebar")
        const searchList = sidebarContent.querySelector(".search-list")
        const dataset = searchList.dataset
        const boundsStr = dataset.bounds
        const isGlobalMode = !boundsStr
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
                    ...focusOptions,
                    // Focus on hover only during global search
                    fitBounds: isGlobalMode,
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

        if (isGlobalMode) {
            // global mode
            if (results.length) {
                focusManyMapObjects(map, groupedElements[0], focusOptions)
                focusMapObject(map, null)
            }
            initialBounds = map.getBounds()
            map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)
        } else {
            // local mode
            initialBounds = null // will be set after flyToBounds animation
            map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)

            const bounds = boundsStr.split(",").map(Number.parseFloat)
            map.flyToBounds(L.latLngBounds(L.latLng(bounds[1], bounds[0]), L.latLng(bounds[3], bounds[2])))
            console.debug("Search focusing on", boundsStr)
        }
    }

    const base = getBaseFetchController(map, "search", onLoaded)
    const baseLoad = base.load
    const baseUnload = base.unload

    base.load = (options) => {
        // Stick the search form and reset search alert
        searchForm.classList.add("sticky-top")
        searchAlert.classList.add("d-none")
        searchAlert.addEventListener("click", onSearchAlertClick, { once: true })
        map.removeEventListener("zoomend moveend", onMapZoomOrMoveEnd)

        // Create the search layer if it doesn't exist
        if (!map.hasLayer(searchLayer)) {
            console.debug("Adding overlay layer", searchLayer.options.layerId)
            map.addLayer(searchLayer)
            map.fire("overlayadd", { layer: searchLayer, name: searchLayer.options.layerId })
        }

        const searchParams = qsParse(location.search.substring(1))
        const query = searchParams.q || searchParams.query || ""
        document.title = getPageTitle(query || defaultTitle)
        setSearchFormQuery(query)

        // Load empty sidebar to ensure proper bbox
        baseLoad({ url: null })
        // Pad the bounds to avoid floating point errors
        const bbox = map.getBounds().pad(-0.01).toBBoxString()
        const url = `/api/partial/search?${qsEncode({
            q: query,
            bbox,
            local_only: options?.local_only ?? false,
        })}`
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

        // Unstick the search form and reset search alert
        searchForm.classList.remove("sticky-top")
        searchAlert.classList.add("d-none")
        searchAlert.removeEventListener("click", onSearchAlertClick)
        map.removeEventListener("zoomend moveend", onMapZoomOrMoveEnd)
    }

    return base
}
