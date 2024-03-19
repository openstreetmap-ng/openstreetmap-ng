import * as L from "leaflet"
import { getActionSidebar, switchActionSidebar } from "../_action-sidebar.js"
import { mapQueryAreaMaxSize } from "../_config.js"
import { getPageTitle } from "../_title.js"
import { zoomPrecision } from "../_utils.js"
import { getLocationFilter } from "../leaflet/_location-filter.js"

/**
 * Create a new export controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getExportController = (map) => {
    const sidebar = getActionSidebar("export")
    const sidebarTitle = sidebar.querySelector(".sidebar-title").textContent
    const minLonInput = sidebar.querySelector("input[name=min_lon]")
    const minLatInput = sidebar.querySelector("input[name=min_lat]")
    const maxLonInput = sidebar.querySelector("input[name=max_lon]")
    const maxLatInput = sidebar.querySelector("input[name=max_lat]")
    const customRegionCheckbox = sidebar.querySelector(".custom-region-check")
    const exportAvailableContainer = sidebar.querySelector(".export-available-container")
    const exportLink = exportAvailableContainer.querySelector(".export-link")
    const exportBaseHref = exportLink.href
    const exportUnavailableContainer = sidebar.querySelector(".export-unavailable-container")
    const exportOverpassLink = sidebar.querySelector(".export-overpass-link")
    const exportOverpassBaseHref = exportOverpassLink.href
    let loaded = false

    // Null values until initialized
    let locationFilter = null

    const updateForm = (minLon, minLat, maxLon, maxLat) => {
        // Update the from availability
        const currentViewAreaSize = (maxLon - minLon) * (maxLat - minLat)
        const isFormAvailable = currentViewAreaSize <= mapQueryAreaMaxSize
        exportAvailableContainer.classList.toggle("d-none", !isFormAvailable)
        exportUnavailableContainer.classList.toggle("d-none", isFormAvailable)

        // Update the export links
        const bboxQueryString = `?bbox=${minLon},${minLat},${maxLon},${maxLat}`
        exportLink.href = exportBaseHref + bboxQueryString
        exportOverpassLink.href = exportOverpassBaseHref + bboxQueryString
    }

    // On map move end, update the inputs
    const onMapMoveEnd = () => {
        // Skip updates if the sidebar is hidden
        if (!loaded) return

        const zoom = map.getZoom()
        const precision = zoomPrecision(zoom)
        const bounds = customRegionCheckbox.checked ? locationFilter.getBounds() : map.getBounds()
        const minLon = bounds.getWest().toFixed(precision)
        const minLat = bounds.getSouth().toFixed(precision)
        const maxLon = bounds.getEast().toFixed(precision)
        const maxLat = bounds.getNorth().toFixed(precision)

        minLonInput.value = minLon
        minLatInput.value = minLat
        maxLonInput.value = maxLon
        maxLatInput.value = maxLat

        updateForm(minLon, minLat, maxLon, maxLat)
    }

    // On custom region checkbox change, enable/disable the location filter
    const onCustomRegionCheckboxChange = () => {
        if (customRegionCheckbox.checked) {
            if (!locationFilter) {
                locationFilter = getLocationFilter({
                    enableButton: false,
                    adjustButton: false,
                })
                locationFilter.addEventListener("change", onMapMoveEnd)
            }

            map.addLayer(locationFilter)

            // By default, location filter is slightly smaller than the current view
            locationFilter.setBounds(map.getBounds().pad(-0.2))
            locationFilter.enable()
        } else {
            map.removeLayer(locationFilter)
        }

        onMapMoveEnd()
    }

    // Listen for events
    map.addEventListener("moveend", onMapMoveEnd)
    customRegionCheckbox.addEventListener("change", onCustomRegionCheckboxChange)

    return {
        load: () => {
            switchActionSidebar(map, "export")
            document.title = getPageTitle(sidebarTitle)
            loaded = true

            // Initial update to set the inputs
            onMapMoveEnd()
        },
        unload: () => {
            // On sidebar hidden, deselect the custom region checkbox
            if (customRegionCheckbox.checked) {
                customRegionCheckbox.checked = false
                customRegionCheckbox.dispatchEvent(new Event("change"))
            }

            loaded = false
        },
    }
}
