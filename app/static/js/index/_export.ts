import type * as L from "leaflet"
import { mapQueryAreaMaxSize } from "../_config"
import { getPageTitle } from "../_title"
import { zoomPrecision } from "../_utils"
import { getLocationFilter } from "../leaflet/_location-filter"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar"
import type { IndexController } from "./_router"

/** Create a new export controller */
export const getExportController = (map: L.Map): IndexController => {
    const sidebar = getActionSidebar("export")
    const sidebarTitle = sidebar.querySelector(".sidebar-title").textContent
    const minLonInput: HTMLInputElement = sidebar.querySelector("input[name=min_lon]")
    const minLatInput: HTMLInputElement = sidebar.querySelector("input[name=min_lat]")
    const maxLonInput: HTMLInputElement = sidebar.querySelector("input[name=max_lon]")
    const maxLatInput: HTMLInputElement = sidebar.querySelector("input[name=max_lat]")
    const customRegionCheckbox: HTMLInputElement = sidebar.querySelector("input.custom-region-check")
    const exportAvailableContainer = sidebar.querySelector(".export-available-container")
    const exportLink: HTMLAnchorElement = exportAvailableContainer.querySelector("a.export-link")
    const exportBaseHref = exportLink.href
    const exportUnavailableContainer = sidebar.querySelector(".export-unavailable-container")
    const exportOverpassLink: HTMLAnchorElement = sidebar.querySelector("a.export-overpass-link")
    const exportOverpassBaseHref = exportOverpassLink.href

    // Null values until initialized
    let locationFilter: any | null = null

    const updateElements = (minLon: number, minLat: number, maxLon: number, maxLat: number) => {
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

    /** On map move end, update the inputs */
    const onMapMoveEnd = () => {
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

        updateElements(minLon, minLat, maxLon, maxLat)
    }

    /** On custom region checkbox change, enable/disable the location filter */
    const onCustomRegionCheckboxChange = () => {
        if (customRegionCheckbox.checked) {
            if (!locationFilter) {
                locationFilter = getLocationFilter()
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

    return {
        load: () => {
            switchActionSidebar(map, "export")
            document.title = getPageTitle(sidebarTitle)

            // Listen for events
            map.addEventListener("moveend", onMapMoveEnd)
            customRegionCheckbox.addEventListener("change", onCustomRegionCheckboxChange)

            // Initial update to set the inputs
            onMapMoveEnd()
        },
        unload: () => {
            // On sidebar hidden, deselect the custom region checkbox
            if (customRegionCheckbox.checked) {
                customRegionCheckbox.checked = false
                customRegionCheckbox.dispatchEvent(new Event("change"))
            }

            map.removeEventListener("moveend", onMapMoveEnd)
            customRegionCheckbox.removeEventListener("change", onCustomRegionCheckboxChange)
        },
    }
}