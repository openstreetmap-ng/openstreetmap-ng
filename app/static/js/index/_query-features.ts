import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import i18next from "i18next"
import * as L from "leaflet"
import { prefersReducedMotion } from "../_config"
import { qsEncode, qsParse } from "../_qs"
import { getPageTitle } from "../_title"
import { isLatitude, isLongitude, requestAnimationFramePolyfill } from "../_utils"
import { queryFeaturesMinZoom } from "../leaflet/_context-menu"
import { focusManyMapObjects, focusMapObject, focusStyles } from "../leaflet/_focus-layer"
import type { LonLatZoom } from "../leaflet/_map-utils"
import { convertRenderElementsData } from "../leaflet/_render-objects"
import { PartialQueryFeaturesParamsSchema } from "../proto/shared_pb"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar"
import type { IndexController } from "./_router"

// TODO: finish this controller

/** Create a new query features controller */
export const getQueryFeaturesController = (map: L.Map): IndexController => {
    const sidebar = getActionSidebar("query-features")
    const sidebarTitle = sidebar.querySelector(".sidebar-title").textContent
    const nearbyContainer = sidebar.querySelector("div.nearby-container")
    const nearbyLoadingHtml = nearbyContainer.innerHTML
    const enclosingContainer = sidebar.querySelector("div.enclosing-container")
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
                const zoom = Math.max(map.getZoom(), queryFeaturesMinZoom)
                return { lon, lat, zoom }
            }
        }
        return null
    }

    /** Configure result actions to handle focus and clicks */
    const configureResultActions = (container: HTMLElement): void => {
        const queryList = container.querySelector("ul.search-list")
        const resultActions = queryList.querySelectorAll("li.social-action")
        const params = fromBinary(PartialQueryFeaturesParamsSchema, base64Decode(queryList.dataset.params))
        for (let i = 0; i < resultActions.length; i++) {
            const resultAction = resultActions[i]
            const render = params.renders[i]
            const elements = convertRenderElementsData(render)

            // TODO: check event order on high activity
            // On hover, focus on the element
            resultAction.addEventListener("mouseenter", () => {
                focusManyMapObjects(map, elements)
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

        const fadeOut = (timestamp?: DOMHighResTimeStamp) => {
            const elapsedTime = (timestamp ?? performance.now()) - animationStart
            let opacity = 1 - Math.min(elapsedTime / animationDuration, 1)
            if (prefersReducedMotion) opacity = opacity > 0 ? 1 : 0
            circle.setStyle({ opacity, fillOpacity: opacity })
            if (opacity > 0 && !abortSignal.aborted) requestAnimationFramePolyfill(fadeOut)
            else map.removeLayer(circle)
        }

        map.addLayer(circle)
        const animationStart = performance.now()
        requestAnimationFramePolyfill(fadeOut)
    }

    /** On sidebar loaded, display content */
    const onSidebarNearbyLoaded = (html: string): void => {
        nearbyContainer.innerHTML = html
        configureResultActions(nearbyContainer)
    }

    /** On sidebar loaded, display content */
    const onSidebarEnclosingLoaded = (html: string): void => {
        enclosingContainer.innerHTML = html
        configureResultActions(enclosingContainer)
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

            abortController?.abort()
            abortController = new AbortController()
            const abortSignal = abortController.signal

            onSidebarLoading(latLng, zoom, abortSignal)

            // Fetch nearby features
            fetch(
                `/api/partial/query/nearby?${qsEncode({
                    lon: lon.toString(),
                    lat: lat.toString(),
                    zoom: zoom.toString(),
                })}`,
                {
                    method: "GET",
                    mode: "same-origin",
                    cache: "no-store", // request params are too volatile to cache
                    signal: abortSignal,
                    priority: "high",
                },
            )
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
            fetch(
                `/api/partial/query/enclosing?${qsEncode({
                    lon: lon.toString(),
                    lat: lat.toString(),
                })}`,
                {
                    method: "GET",
                    mode: "same-origin",
                    cache: "no-store", // request params are too volatile to cache
                    signal: abortSignal,
                    priority: "high",
                },
            )
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
            abortController?.abort()
            abortController = null
            focusMapObject(map, null)
        },
    }
}
