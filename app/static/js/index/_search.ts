import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import i18next from "i18next"
import * as L from "leaflet"
import { qsEncode, qsParse } from "../_qs"
import { getPageTitle } from "../_title"
import type { Bounds } from "../_types"
import { isLongitude, zoomPrecision } from "../_utils"
import { type FocusOptions, focusManyMapObjects, focusMapObject } from "../leaflet/_focus-layer"
import { type LayerId, getOverlayLayerById } from "../leaflet/_layers"
import { getMapAlert } from "../leaflet/_map-utils"
import { convertRenderObjectsData } from "../leaflet/_render-objects"
import { getLatLngBoundsIntersection, getLatLngBoundsSize, getMarkerIcon } from "../leaflet/_utils"
import { PartialSearchParamsSchema } from "../proto/shared_pb"
import { getBaseFetchController } from "./_base-fetch"
import type { IndexController } from "./_router"
import { routerNavigateStrict } from "./_router"
import { setSearchFormQuery } from "./_search-form"

const markerOpacity = 0.8
const searchAlertChangeThreshold = 0.9
const searchLayerId = "search" as LayerId
const focusOptions: FocusOptions = {
    padBounds: 0.5,
    maxZoom: 14,
    intersects: true,
    proportionCheck: false,
}

/** Create a new search controller */
export const getSearchController = (map: L.Map): IndexController => {
    const searchLayer = getOverlayLayerById(searchLayerId) as L.FeatureGroup
    const searchForm = document.querySelector("form.search-form")
    const searchAlert = getMapAlert("search-alert")
    const searchTitle = i18next.t("site.search.search")
    const whereIsThisTitle = i18next.t("site.search.where_am_i")

    let initialBounds: L.LatLngBounds | null = null
    let whereIsThisMode = false

    /** On search alert click, reload the search with the new area */
    const onSearchAlertClick = () => {
        console.debug("Searching within new area")
        controller.unload()
        if (whereIsThisMode) {
            const zoom = map.getZoom()
            const precision = zoomPrecision(zoom)
            const latLng = map.getCenter()
            controller.load({
                lon: latLng.lng.toFixed(precision),
                lat: latLng.lat.toFixed(precision),
                zoom: zoom.toString(),
            })
        } else {
            controller.load({ localOnly: "1" })
        }
    }

    /** On map update, check if view was changed and show alert if so */
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

    const base = getBaseFetchController(map, "search", (sidebarContent) => {
        const sidebar = sidebarContent.closest(".sidebar")
        const searchList = sidebarContent.querySelector("ul.search-list")
        const results = searchList.querySelectorAll("li.social-action")

        const params = fromBinary(PartialSearchParamsSchema, base64Decode(searchList.dataset.params))
        const globalMode = !params.boundsStr
        whereIsThisMode = params.whereIsThis

        const layers: L.Marker[] = []
        for (let i = 0; i < results.length; i++) {
            const elements = convertRenderObjectsData(params.renders[i])
            const div = results[i]

            const dataset = div.dataset
            const type = dataset.type
            const id = dataset.id
            const lon = Number.parseFloat(dataset.lon)
            const lat = Number.parseFloat(dataset.lat)

            const marker = isLongitude(lon)
                ? L.marker(L.latLng(lat, lon), {
                      icon: getMarkerIcon("red", true),
                      opacity: markerOpacity,
                  })
                : null

            /** On mouse enter, scroll result into view and focus elements */
            const onMouseover = (): void => {
                const sidebarRect = sidebar.getBoundingClientRect()
                const resultRect = div.getBoundingClientRect()
                const isVisible = resultRect.top >= sidebarRect.top && resultRect.bottom <= sidebarRect.bottom
                if (!isVisible) div.scrollIntoView({ behavior: "smooth", block: "center" })

                div.classList.add("hover")
                focusManyMapObjects(map, elements, {
                    ...focusOptions,
                    // Focus on hover only during global search
                    fitBounds: globalMode,
                })
                marker?.setOpacity(1)
            }

            /** On mouse leave, unfocus elements */
            const onMouseout = () => {
                div.classList.remove("hover")
                focusMapObject(map, null)
                marker?.setOpacity(markerOpacity)
            }

            // Listen for events
            div.addEventListener("mouseover", onMouseover)
            div.addEventListener("mouseout", onMouseout)
            if (marker) {
                marker.addEventListener("mouseover", onMouseover)
                marker.addEventListener("mouseout", onMouseout)

                // On marker click, navigate to the element
                marker.addEventListener("click", (e) => {
                    const url = `/${type}/${id}`
                    if (e.originalEvent.ctrlKey) {
                        window.open(url, "_blank")
                    } else {
                        routerNavigateStrict(url)
                    }
                })
                layers.push(marker)
            }
        }

        searchLayer.clearLayers()
        searchLayer.addLayer(L.layerGroup(layers))
        console.debug("Search showing", results.length, "results")

        if (globalMode) {
            // global mode
            if (results.length) {
                const elements = convertRenderObjectsData(params.renders[0])
                focusManyMapObjects(map, elements, focusOptions)
                focusMapObject(map, null)
            }
            initialBounds = map.getBounds()
            map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)
        } else {
            // local mode
            initialBounds = null // will be set after flyToBounds animation
            map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)

            console.debug("Search focusing on", params.boundsStr)
            const bounds = params.boundsStr.split(",").map(Number.parseFloat) as Bounds
            map.flyToBounds(L.latLngBounds(L.latLng(bounds[1], bounds[0]), L.latLng(bounds[3], bounds[2])))
        }
    })

    const controller: IndexController = {
        load: (options) => {
            // Stick the search form and reset search alert
            searchForm.classList.add("sticky-top")
            searchAlert.classList.add("d-none")
            searchAlert.addEventListener("click", onSearchAlertClick, { once: true })
            map.removeEventListener("zoomend moveend", onMapZoomOrMoveEnd)

            // Create the search layer if it doesn't exist
            if (!map.hasLayer(searchLayer)) {
                console.debug("Adding overlay layer", searchLayerId)
                map.addLayer(searchLayer)
                map.fire("overlayadd", { layer: searchLayer, name: searchLayerId })
            }

            const searchParams = qsParse(window.location.search.substring(1))
            const query = searchParams.q || searchParams.query || ""
            const lon = options?.lon ?? searchParams.lon
            const lat = options?.lat ?? searchParams.lat

            console.log(query, lon, lat, options, searchParams)
            if (!query && lon && lat) {
                document.title = getPageTitle(whereIsThisTitle)
                setSearchFormQuery(null)

                const zoom = options?.zoom ?? searchParams.zoom ?? map.getZoom().toString()
                const url = `/api/partial/where-is-this?${qsEncode({ lon, lat, zoom })}`
                base.load({ url })
            } else {
                document.title = getPageTitle(query || searchTitle)
                setSearchFormQuery(query)

                // Load empty sidebar to ensure proper bbox
                base.load({ url: null })
                // Pad the bounds to avoid floating point errors
                const bbox = map.getBounds().pad(-0.01).toBBoxString()
                const url = `/api/partial/search?${qsEncode({
                    q: query,
                    bbox,
                    // biome-ignore lint/style/useNamingConvention:
                    local_only: Boolean(options?.localOnly).toString(),
                })}`
                base.load({ url })
            }
        },
        unload: () => {
            base.unload()

            // Remove the search layer
            if (map.hasLayer(searchLayer)) {
                console.debug("Removing overlay layer", searchLayerId)
                map.removeLayer(searchLayer)
                map.fire("overlayremove", { layer: searchLayer, name: searchLayerId })
            }

            // Clear the search layer
            searchLayer.clearLayers()

            // Unstick the search form and reset search alert
            searchForm.classList.remove("sticky-top")
            searchAlert.classList.add("d-none")
            map.removeEventListener("zoomend moveend", onMapZoomOrMoveEnd)
        },
    }
    return controller
}
