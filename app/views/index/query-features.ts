import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import { getActionSidebar, switchActionSidebar } from "@index/_action-sidebar"
import { prefersReducedMotion } from "@lib/config"
import { isLatitude, isLongitude, isZoom } from "@lib/coords"
import { QUERY_FEATURES_MIN_ZOOM } from "@lib/map/controls/query-features"
import { type FocusLayerPaint, focusObjects } from "@lib/map/layers/focus-layer"
import {
    addMapLayer,
    emptyFeatureCollection,
    getExtendedLayerId,
    type LayerId,
    layersConfig,
    removeMapLayer,
} from "@lib/map/layers/layers"
import { convertRenderElementsData } from "@lib/map/render-objects"
import { requestAnimationFramePolyfill } from "@lib/polyfills"
import { PartialQueryFeaturesParamsSchema } from "@lib/proto/shared_pb"
import { qsEncode, qsParse } from "@lib/qs"
import { setPageTitle } from "@lib/title"
import { memoize } from "@std/cache/memoize"
import type { FeatureCollection } from "geojson"
import i18next from "i18next"
import { type GeoJSONSource, LngLat, type Map as MaplibreMap } from "maplibre-gl"

const LAYER_ID = "query-features" as LayerId
const THEME_COLOR = "#f60"
layersConfig.set(LAYER_ID, {
    specification: {
        type: "geojson",
        data: emptyFeatureCollection,
    },
    layerTypes: ["fill", "line"],
    layerOptions: {
        paint: {
            "fill-opacity": 0,
            "fill-color": THEME_COLOR,
            "line-opacity": 0,
            "line-color": THEME_COLOR,
            "line-width": 4,
        },
    },
    priority: 170,
})
const focusPaint: FocusLayerPaint = {
    "fill-color": THEME_COLOR,
    "fill-opacity": 0.5,
    "line-color": THEME_COLOR,
    "line-opacity": 1,
    "line-width": 4,
    "circle-radius": 10,
    "circle-color": THEME_COLOR,
    "circle-opacity": 0.4,
    "circle-stroke-color": THEME_COLOR,
    "circle-stroke-opacity": 1,
    "circle-stroke-width": 3,
}

export const getQueryFeaturesController = (map: MaplibreMap) => {
    const source = map.getSource<GeoJSONSource>(LAYER_ID)!
    const sidebar = getActionSidebar("query-features")
    const sidebarTitle = sidebar.querySelector(".sidebar-title")!.textContent
    const nearbyContainer = sidebar.querySelector("div.nearby-container")!
    const nearbyLoadingHtml = nearbyContainer.innerHTML
    const emptyText = i18next.t("javascripts.query.nothing_found")
    const queryFeaturesButton = map
        .getContainer()
        .querySelector(".maplibregl-ctrl.query-features button")!

    let abortController: AbortController | undefined

    const getURLQueryPosition = () => {
        const searchParams = qsParse(window.location.search)
        if (searchParams.lon && searchParams.lat) {
            const lon = Number.parseFloat(searchParams.lon)
            const lat = Number.parseFloat(searchParams.lat)
            const zoom = Math.max(
                searchParams.zoom
                    ? Number.parseFloat(searchParams.zoom)
                    : map.getZoom(),
                QUERY_FEATURES_MIN_ZOOM,
            )
            if (isLongitude(lon) && isLatitude(lat) && isZoom(zoom)) {
                return { lon, lat, zoom }
            }
        }
        return null
    }

    /** Configure result actions to handle focus and clicks */
    const configureResultActions = (container: HTMLElement) => {
        const queryList = container.querySelector("ul.search-list")!
        const resultActions = queryList.querySelectorAll("li.social-entry.clickable")
        const params = fromBinary(
            PartialQueryFeaturesParamsSchema,
            base64Decode(queryList.dataset.params!),
        )
        for (let i = 0; i < resultActions.length; i++) {
            const resultAction = resultActions[i]
            const render = params.renders[i]
            const elements = memoize(() => convertRenderElementsData(render))
            resultAction.addEventListener("mouseenter", () =>
                focusObjects(map, elements(), focusPaint),
            )
            resultAction.addEventListener("mouseleave", () => focusObjects(map)) // remove focus
        }
    }

    /** On sidebar loading, display loading content and show map animation */
    const onSidebarLoading = (
        center: LngLat,
        zoom: number,
        abortSignal: AbortSignal,
    ) => {
        nearbyContainer.innerHTML = nearbyLoadingHtml

        const radiusMeters = 10 * 1.5 ** (19 - zoom)
        console.debug("QueryFeatures: Radius", radiusMeters, "meters")
        source.setData(getCircleFeature(center, radiusMeters))

        // Fade out circle smoothly
        const animationDuration = 750
        const fillLayerId = getExtendedLayerId(LAYER_ID, "fill")
        const lineLayerId = getExtendedLayerId(LAYER_ID, "line")
        const fadeOut = (timestamp: DOMHighResTimeStamp) => {
            if (timestamp < animationStart) animationStart = timestamp
            const elapsedTime = timestamp - animationStart
            let opacity = 1 - Math.min(elapsedTime / animationDuration, 1)
            if (prefersReducedMotion()) opacity = opacity > 0 ? 1 : 0
            map.setPaintProperty(fillLayerId, "fill-opacity", opacity * 0.4)
            map.setPaintProperty(lineLayerId, "line-opacity", opacity)
            if (opacity > 0 && !abortSignal.aborted)
                requestAnimationFramePolyfill(fadeOut)
            else {
                removeMapLayer(map, LAYER_ID, false)
                source.setData(emptyFeatureCollection)
            }
        }
        addMapLayer(map, LAYER_ID, false)
        let animationStart = performance.now()
        requestAnimationFramePolyfill(fadeOut)
    }

    /** On sidebar loaded, display content */
    const onSidebarLoaded = (html: string) => {
        nearbyContainer.innerHTML = html
        configureResultActions(nearbyContainer)
    }

    return {
        load: async () => {
            switchActionSidebar(map, sidebar)
            setPageTitle(sidebarTitle)

            const position = getURLQueryPosition()
            if (!position) {
                nearbyContainer.textContent = emptyText
                return
            }
            const { lon, lat, zoom } = position

            // Focus on the query area if it's offscreen
            const center = new LngLat(lon, lat)
            if (!map.getBounds().contains(center)) {
                map.jumpTo({ center, zoom })
            }

            abortController?.abort()
            abortController = new AbortController()
            const abortSignal = abortController.signal

            // Fetch nearby features
            const zoomFloor = zoom | 0
            onSidebarLoading(center, zoomFloor, abortSignal)
            try {
                const resp = await fetch(
                    `/partial/query/nearby${qsEncode({
                        lon: lon.toString(),
                        lat: lat.toString(),
                        zoom: zoomFloor.toString(),
                    })}`,
                    { signal: abortSignal, priority: "high" },
                )
                onSidebarLoaded(await resp.text())
            } catch (error) {
                if (error.name === "AbortError") return
                console.error("QueryFeatures: Failed to fetch", error)
                onSidebarLoaded(
                    i18next.t("javascripts.query.error", {
                        server: window.location.host,
                        error: error.message,
                    }),
                )
            }
        },
        unload: (newPath?: string) => {
            // On navigation, deactivate query features button
            if (
                !newPath?.startsWith("/query") &&
                queryFeaturesButton.classList.contains("active")
            ) {
                console.debug("QueryFeatures: Deactivating button")
                queryFeaturesButton.click()
            }
            abortController?.abort()
            focusObjects(map)
        },
    }
}

const getCircleFeature = (
    { lng, lat }: LngLat,
    radiusMeters: number,
    vertices = 36,
): FeatureCollection => {
    const radiusLat = metersToDegrees(radiusMeters)
    const radiusLon = radiusLat / Math.cos((lat * Math.PI) / 180)
    const coords: number[][] = []

    const delta = (2 * Math.PI) / vertices
    const cosDelta = Math.cos(delta)
    const sinDelta = Math.sin(delta)
    let cosTheta = 1 // cos(0) = 1
    let sinTheta = 0 // sin(0) = 0

    for (let i = 0; i < vertices; i++) {
        const x = lng + radiusLon * cosTheta
        const y = lat + radiusLat * sinTheta
        coords.push([x, y])

        const newCosTheta = cosTheta * cosDelta - sinTheta * sinDelta
        const newSinTheta = sinTheta * cosDelta + cosTheta * sinDelta
        cosTheta = newCosTheta
        sinTheta = newSinTheta
    }
    coords.push(coords[0])

    return {
        type: "FeatureCollection",
        features: [
            {
                type: "Feature",
                properties: {},
                geometry: {
                    type: "Polygon",
                    coordinates: [coords],
                },
            },
            {
                type: "Feature",
                properties: {},
                geometry: {
                    type: "LineString",
                    coordinates: coords,
                },
            },
        ],
    }
}

const metersToDegrees = (meters: number) => meters / (6371000 / 57.29577951308232) // R / (180 / pi)
