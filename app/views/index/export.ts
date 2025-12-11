import { getActionSidebar, switchActionSidebar } from "@index/_action-sidebar"
import { MAP_QUERY_AREA_MAX_SIZE } from "@lib/config"
import { zoomPrecision } from "@lib/coords"
import { padLngLatBounds } from "@lib/map/bounds"
import { LocationFilterControl } from "@lib/map/controls/location-filter"
import { setPageTitle } from "@lib/title"
import { assertExists } from "@std/assert"
import { throttle } from "@std/async/unstable-throttle"
import type { Map as MaplibreMap } from "maplibre-gl"

export const getExportController = (map: MaplibreMap) => {
    const sidebar = getActionSidebar("export")
    const sidebarTitle = sidebar.querySelector(".sidebar-title")!.textContent
    const minLonInput = sidebar.querySelector("input[name=min_lon]")!
    const minLatInput = sidebar.querySelector("input[name=min_lat]")!
    const maxLonInput = sidebar.querySelector("input[name=max_lon]")!
    const maxLatInput = sidebar.querySelector("input[name=max_lat]")!
    const customRegionCheckbox = sidebar.querySelector("input.custom-region-check")!
    const exportAvailableContainer = sidebar.querySelector(
        ".export-available-container",
    )!
    const exportLink = exportAvailableContainer.querySelector("a.export-link")!
    const exportBaseHref = exportLink.href
    const exportUnavailableContainer = sidebar.querySelector(
        ".export-unavailable-container",
    )!
    const exportOverpassLink = sidebar.querySelector("a.export-overpass-link")!
    const exportOverpassBaseHref = exportOverpassLink.href

    let locationFilter: LocationFilterControl | undefined

    // On custom region checkbox change, enable/disable the location filter
    customRegionCheckbox.addEventListener("change", () => {
        console.debug(
            "Export: Custom region checkbox changed",
            customRegionCheckbox.checked,
        )
        if (customRegionCheckbox.checked) {
            if (!locationFilter) {
                locationFilter = new LocationFilterControl()
                locationFilter.addOnRenderHandler(
                    throttle(updateState, 250, { ensureLastCall: true }),
                )
            }
            // By default, location filter is slightly smaller than the current view
            locationFilter.addTo(map, padLngLatBounds(map.getBounds(), -0.2))
        } else {
            assertExists(locationFilter)
            locationFilter.remove()
        }
        updateState()
    })

    const updateState = () => {
        const precision = zoomPrecision(map.getZoom())
        const bounds = customRegionCheckbox.checked
            ? locationFilter!.getBounds()
            : map.getBounds()
        const [[minLon, minLat], [maxLon, maxLat]] = bounds
            .adjustAntiMeridian()
            .toArray()
        minLonInput.value = minLon.toFixed(precision)
        minLatInput.value = minLat.toFixed(precision)
        maxLonInput.value = maxLon.toFixed(precision)
        maxLatInput.value = maxLat.toFixed(precision)
        updateElements(minLon, minLat, maxLon, maxLat)
    }

    const updateElements = (
        minLon: number,
        minLat: number,
        maxLon: number,
        maxLat: number,
    ) => {
        // Update the form availability
        const currentViewAreaSize = (maxLon - minLon) * (maxLat - minLat)
        const isFormAvailable = currentViewAreaSize <= MAP_QUERY_AREA_MAX_SIZE
        exportAvailableContainer.classList.toggle("d-none", !isFormAvailable)
        exportUnavailableContainer.classList.toggle("d-none", isFormAvailable)

        // Update the export links
        const bboxQueryString = `?bbox=${minLon},${minLat},${maxLon},${maxLat}`
        exportLink.href = exportBaseHref + bboxQueryString
        exportOverpassLink.href = exportOverpassBaseHref + bboxQueryString
    }

    return {
        load: () => {
            switchActionSidebar(map, sidebar)
            setPageTitle(sidebarTitle)
            map.on("moveend", updateState)
            updateState()
        },
        unload: () => {
            map.off("moveend", updateState)
            // On sidebar hidden, deselect the custom region checkbox
            if (customRegionCheckbox.checked) {
                customRegionCheckbox.checked = false
                customRegionCheckbox.dispatchEvent(new Event("change"))
            }
        },
    }
}
