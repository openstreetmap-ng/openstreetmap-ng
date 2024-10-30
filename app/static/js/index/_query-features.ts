import i18next from "i18next"
import * as L from "leaflet"
import { qsEncode, qsParse } from "../_qs"
import { getPageTitle } from "../_title"
import { isLatitude, isLongitude } from "../_utils"
import { focusMapObject, focusStyles } from "../leaflet/_focus-layer"
import type { LonLatZoom } from "../leaflet/_map-utils"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar"
import type { IndexController } from "./_router"

// TODO: finish this controller

/** Create a new query features controller */
export const getQueryFeaturesController = (map: L.Map): IndexController => {
    const sidebar = getActionSidebar("query-features")
    const sidebarTitle = sidebar.querySelector(".sidebar-title").textContent
    const nearbyContainer = sidebar.querySelector("div.nearby-container")
    const nearbyLoadingHtml = nearbyContainer.innerHTML
    const enclosingContainer = sidebar.querySelector(".enclosing-container")
    const enclosingLoadingHtml = enclosingContainer.innerHTML
    const emptyText = i18next.t("javascripts.query.nothing_found")

    let abortController: AbortController | null = null

    /** Get query position from URL */
    const getURLQueryPosition = (): LonLatZoom | null => {
        const searchParams = qsParse(location.search.substring(1))
        if (searchParams.lon && searchParams.lat) {
            const lon = Number.parseFloat(searchParams.lon)
            const lat = Number.parseFloat(searchParams.lat)
            if (isLongitude(lon) && isLatitude(lat)) {
                const zoom = map.getZoom()
                return { lon, lat, zoom }
            }
        }
        return null
    }

    /** Configure result actions to handle focus and clicks */
    const configureResultActions = (container: HTMLElement): void => {
        const resultActions = container.querySelectorAll("li.social-action")
        for (const resultAction of resultActions) {
            // Get params
            const params = JSON.parse(resultAction.dataset.params)
            const mainElementType = params.type
            const mainElementId = params.id
            const elements = params.elements

            // TODO: leaflet elements
            const elementMap = parseElements(elements)
            const mainElement = elementMap[mainElementType].get(mainElementId)

            // TODO: check event order on high activity
            // On hover, focus on the element
            resultAction.addEventListener("mouseenter", () => {
                focusMapObject(map, mainElement)
            })
            // On hover end, unfocus the element
            resultAction.addEventListener("mouseleave", () => {
                focusMapObject(map, null)
            })
        }
    }

    /** On sidebar loading, display loading content and show map animation */
    const onSidebarLoading = (latLng: L.LatLng, zoom: number, abortSignal: AbortSignal): void => {
        nearbyContainer.innerHTML = nearbyLoadingHtml
        enclosingContainer.innerHTML = enclosingLoadingHtml

        // Fade out circle smoothly
        const radius = 10 * 1.5 ** (19 - zoom)
        const circle = L.circle(latLng, { ...focusStyles.element, pane: "overlayPane", radius })
        const animationDuration = 750
        // TODO: reduced motion

        // NOTE: remove polyfill when requestAnimationFrame
        const requestAnimationFrame_ = window.requestAnimationFrame || ((callback) => window.setTimeout(callback, 30))

        const fadeOut = (timestamp?: DOMHighResTimeStamp) => {
            const elapsedTime = (timestamp ?? performance.now()) - animationStart
            const opacity = 1 - Math.min(elapsedTime / animationDuration, 1)
            circle.setStyle({ opacity, fillOpacity: opacity })
            if (opacity > 0 && !abortSignal.aborted) requestAnimationFrame_(fadeOut)
            else map.removeLayer(circle)
        }

        map.addLayer(circle)
        const animationStart = performance.now()
        requestAnimationFrame_(fadeOut)
    }

    /** On sidebar loaded, display content */
    const onSidebarNearbyLoaded = (html: string): void => {
        nearbyContainer.innerHTML = html
        configureResultActions(nearbyContainer)
    }

    /** On sidebar loaded, display content */
    const onSidebarEnclosingLoaded = (html: string): void => {
        enclosingContainer.innerHTML = html
    }

    // TODO: on tab close, disable query mode
    return {
        load: () => {
            switchActionSidebar(map, "query-features")
            document.title = getPageTitle(sidebarTitle)

            const position = getURLQueryPosition()
            if (!position) {
                nearbyContainer.textContent = emptyText
                enclosingContainer.textContent = emptyText
                return
            }
            const { lon, lat, zoom } = position

            // Focus on the query area if it's offscreen
            const latLng = L.latLng(lat, lon)
            if (!map.getBounds().contains(latLng)) {
                map.panTo(latLng, { animate: false })
            }

            if (abortController) abortController.abort()
            abortController = new AbortController()
            const abortSignal = abortController.signal

            onSidebarLoading(latLng, zoom, abortSignal)

            // Fetch nearby features
            const queryString = qsEncode({ lon: lon.toString(), lat: lat.toString(), zoom: zoom.toString() })

            fetch(`/api/partial/query/nearby?${queryString}`, {
                method: "GET",
                mode: "same-origin",
                cache: "no-store", // request params are too volatile to cache
                signal: abortSignal,
                priority: "high",
            })
                .then(async (resp) => {
                    onSidebarNearbyLoaded(await resp.text())
                })
                .catch((error) => {
                    if (error.name === "AbortError") return
                    console.error("Failed to fetch nearby features", error)
                    // TODO: nicer error html
                    onSidebarNearbyLoaded(
                        i18next.t("javascripts.query.error", {
                            server: "OpenStreetMap",
                            error: error.message,
                        }),
                    )
                })

            // Fetch enclosing features
            fetch(`/api/partial/query/enclosing?${queryString}`, {
                method: "GET",
                mode: "same-origin",
                cache: "no-store", // request params are too volatile to cache
                signal: abortSignal,
                priority: "high",
            })
                .then(async (resp) => {
                    onSidebarEnclosingLoaded(await resp.text())
                })
                .catch((error) => {
                    if (error.name === "AbortError") return
                    console.error("Failed to fetch enclosing features", error)
                    onSidebarEnclosingLoaded(
                        i18next.t("javascripts.query.error", {
                            server: "OpenStreetMap",
                            error: error.message,
                        }),
                    )
                })
        },
        unload: () => {
            if (abortController) abortController.abort()
            abortController = null
            focusMapObject(map, null)
        },
    }
}
