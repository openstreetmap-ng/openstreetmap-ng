import * as L from "leaflet"
import { getActionSidebar, switchActionSidebar } from "../_action-sidebar.js"
import { mapQueryAreaMaxSize } from "../_config.js"
import { getPageTitle } from "../_title.js"
import { isLatitude, isLongitude, zoomPrecision } from "../_utils.js"
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
    const exportBaseHref = exportLink.getAttribute("href")
    const exportUnavailableContainer = sidebar.querySelector(".export-unavailable-container")
    const exportOverpassLink = sidebar.querySelector(".export-overpass-link")
    const exportOverpassBaseHref = exportOverpassLink.getAttribute("href")
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
        exportLink.setAttribute("href", exportBaseHref + bboxQueryString)
        exportOverpassLink.setAttribute("href", exportOverpassBaseHref + bboxQueryString)
    }

    // On input change, enable the custom region and update the filter's bounds
    const onInput = () => {
        const minLon = parseFloat(minLonInput.value)
        const minLat = parseFloat(minLatInput.value)
        const maxLon = parseFloat(maxLonInput.value)
        const maxLat = parseFloat(maxLatInput.value)

        const isMinLonValid = isLongitude(minLon)
        const isMinLatValid = isLatitude(minLat)
        const isMaxLonValid = isLongitude(maxLon)
        const isMaxLatValid = isLatitude(maxLat)

        // biome-ignore lint/complexity/useSimplifiedLogicExpression:
        minLonInput.classList.toggle("is-invalid", !isMinLonValid && !minLonInput.validity.valueMissing)
        // biome-ignore lint/complexity/useSimplifiedLogicExpression:
        minLatInput.classList.toggle("is-invalid", !isMinLatValid && !minLatInput.validity.valueMissing)
        // biome-ignore lint/complexity/useSimplifiedLogicExpression:
        maxLonInput.classList.toggle("is-invalid", !isMaxLonValid && !maxLonInput.validity.valueMissing)
        // biome-ignore lint/complexity/useSimplifiedLogicExpression:
        maxLatInput.classList.toggle("is-invalid", !isMaxLatValid && !maxLatInput.validity.valueMissing)

        // Skip processing invalid values
        if (!(isMinLonValid && isMinLatValid && isMaxLonValid && isMaxLatValid)) return

        if (!customRegionCheckbox.checked) {
            customRegionCheckbox.checked = true
            customRegionCheckbox.dispatchEvent(new Event("change"))
        }

        // Update the filter's bounds
        locationFilter.setBounds(L.latLngBounds([minLat, minLon], [maxLat, maxLon]))

        updateForm(minLon, minLat, maxLon, maxLat)
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
    for (const input of [minLonInput, minLatInput, maxLonInput, maxLatInput]) {
        input.addEventListener("input", onInput)
    }
    customRegionCheckbox.addEventListener("change", onCustomRegionCheckboxChange)

    return {
        load: () => {
            switchActionSidebar("export")
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
