import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import type { Feature } from "geojson"
import i18next from "i18next"
import { type GeoJSONSource, LngLatBounds, type Map as MaplibreMap } from "maplibre-gl"
import { getMapAlert } from "../lib/map/alert"
import { clearMapHover, setMapHover } from "../lib/map/hover"
import { loadMapImage, markerRedImageUrl } from "../lib/map/image"
import {
    type FocusLayerPaint,
    type FocusOptions,
    focusObjects,
} from "../lib/map/layers/focus-layer"
import {
    addMapLayer,
    emptyFeatureCollection,
    type LayerId,
    layersConfig,
    removeMapLayer,
} from "../lib/map/layers/layers"
import { convertRenderElementsData } from "../lib/map/render-objects"
import {
    getLngLatBoundsIntersection,
    getLngLatBoundsSize,
    padLngLatBounds,
} from "../lib/map/utils"
import { PartialSearchParamsSchema } from "../lib/proto/shared_pb"
import { qsEncode, qsParse } from "../lib/qs"
import { setPageTitle } from "../lib/title"
import type { Bounds, OSMObject } from "../lib/types"
import {
    beautifyZoom,
    isLatitude,
    isLongitude,
    staticCache,
    zoomPrecision,
} from "../lib/utils"
import { getBaseFetchController } from "./_base-fetch"
import type { IndexController } from "./_router"
import { setSearchFormQuery } from "./search-form"

const layerId = "search" as LayerId
layersConfig.set(layerId, {
    specification: {
        type: "geojson",
        data: emptyFeatureCollection,
    },
    layerTypes: ["symbol"],
    layerOptions: {
        layout: {
            "icon-image": "marker-red",
            "icon-allow-overlap": true,
            "icon-size": 41 / 128,
            "icon-padding": 0,
            "icon-anchor": "bottom",
        },
        paint: {
            "icon-opacity": [
                "case",
                ["boolean", ["feature-state", "hover"], false],
                1,
                0.8,
            ],
        },
    },
    priority: 150,
})

const themeColor = "#f60"
const focusPaint: FocusLayerPaint = Object.freeze({
    "fill-color": themeColor,
    "fill-opacity": 0.5,
    "line-color": themeColor,
    "line-opacity": 1,
    "line-width": 4,
    "circle-radius": 10,
    "circle-color": themeColor,
    "circle-opacity": 0.4,
    "circle-stroke-color": themeColor,
    "circle-stroke-opacity": 1,
    "circle-stroke-width": 3,
})
const focusOptions: FocusOptions = Object.freeze({
    padBounds: 0.5,
    maxZoom: 14,
    intersects: true,
    proportionCheck: false,
})

const searchAlertChangeThreshold = 0.9

/** Create a new search controller */
export const getSearchController = (map: MaplibreMap): IndexController => {
    const source = map.getSource(layerId) as GeoJSONSource
    const searchForm = document.querySelector("form.search-form")
    const searchAlert = getMapAlert("search-alert")
    const searchTitle = i18next.t("site.search.search")
    const whereIsThisTitle = i18next.t("site.search.where_am_i")

    let results: NodeListOf<HTMLLIElement> | null = null
    let setHover: ((id: number, hover: boolean) => void) | null = null
    let initialBounds: LngLatBounds | null = null
    let whereIsThisMode = false

    // On feature click, navigate to the note
    map.on("click", layerId, (e) => {
        const result = results[e.features[0].id as number]
        const target = result.querySelector("a.stretched-link")
        target.click()
    })

    let hoveredFeatureId: number | null = null
    map.on("mousemove", layerId, (e) => {
        const featureId = e.features[0].id
        if (hoveredFeatureId) {
            if (hoveredFeatureId === featureId) return
            setHover(hoveredFeatureId, false)
        } else {
            setMapHover(map, layerId)
        }
        hoveredFeatureId = featureId as number
        setHover(hoveredFeatureId, true)
    })
    map.on("mouseleave", layerId, () => {
        setHover?.(hoveredFeatureId, false)
        hoveredFeatureId = null
        clearMapHover(map, layerId)
    })

    /** On search alert click, reload the search with the new area */
    const onSearchAlertClick = () => {
        console.debug("Searching within new area")
        controller.unload()
        if (whereIsThisMode) {
            const center = map.getCenter()
            const zoom = map.getZoom()
            const precision = zoomPrecision(zoom)
            controller.load({
                lon: center.lng.toFixed(precision),
                lat: center.lat.toFixed(precision),
                zoom: beautifyZoom(zoom),
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

        const initialBoundsSize = getLngLatBoundsSize(initialBounds)
        const mapBounds = map.getBounds()
        const mapBoundsSize = getLngLatBoundsSize(mapBounds)
        const intersectionBounds = getLngLatBoundsIntersection(initialBounds, mapBounds)
        const intersectionBoundsSize = getLngLatBoundsSize(intersectionBounds)
        const proportion = Math.min(
            intersectionBoundsSize / mapBoundsSize,
            intersectionBoundsSize / initialBoundsSize,
        )
        if (proportion > searchAlertChangeThreshold) return

        searchAlert.classList.remove("d-none")
        map.off("moveend", onMapZoomOrMoveEnd)
    }

    const base = getBaseFetchController(map, "search", (sidebarContent) => {
        const sidebar = sidebarContent.closest(".sidebar")
        const searchList = sidebarContent.querySelector("ul.search-list")
        results = searchList.querySelectorAll("li.social-entry.clickable")

        const params = fromBinary(
            PartialSearchParamsSchema,
            base64Decode(searchList.dataset.params),
        )
        const globalMode = !params.boundsStr
        whereIsThisMode = params.whereIsThis

        const elements: (() => OSMObject[])[] = []
        const features: Feature[] = []
        for (let i = 0; i < results.length; i++) {
            const result = results[i]
            result.addEventListener("mouseenter", () => setHover(i, true))
            result.addEventListener("mouseleave", () => setHover?.(i, false))

            // Lazily convert render elements data
            elements.push(
                staticCache(() => convertRenderElementsData(params.renders[i])),
            )

            const dataset = result.dataset
            const lon = Number.parseFloat(dataset.lon)
            const lat = Number.parseFloat(dataset.lat)
            if (isLongitude(lon) && isLatitude(lat)) {
                // Not all results have a central point
                features.push({
                    type: "Feature",
                    id: i,
                    properties: {},
                    geometry: {
                        type: "Point",
                        coordinates: [lon, lat],
                    },
                })
            }
        }
        source.setData({ type: "FeatureCollection", features })
        addMapLayer(map, layerId)
        console.debug("Search layer showing", results.length, "results")

        /** Set the hover state of the search features */
        setHover = (id: number, hover: boolean): void => {
            const result = results[id]
            result?.classList.toggle("hover", hover)

            map.setFeatureState({ source: layerId, id: id }, { hover })

            if (hover && result) {
                // Scroll result into view
                const sidebarRect = sidebar.getBoundingClientRect()
                const resultRect = result.getBoundingClientRect()
                const isVisible =
                    resultRect.top >= sidebarRect.top &&
                    resultRect.bottom <= sidebarRect.bottom
                if (!isVisible)
                    result.scrollIntoView({ behavior: "smooth", block: "center" })
                focusObjects(map, elements[id](), focusPaint, null, {
                    ...focusOptions,
                    // Focus on hover only during global search
                    fitBounds: globalMode,
                })
            } else {
                focusObjects(map)
            }
        }

        if (globalMode) {
            // global mode
            if (results.length) {
                focusObjects(map, elements[0](), focusPaint, null, focusOptions)
                focusObjects(map)
            }
            initialBounds = map.getBounds()
            map.on("moveend", onMapZoomOrMoveEnd)
        } else {
            // local mode
            initialBounds = null // will be set after flyToBounds animation
            map.on("moveend", onMapZoomOrMoveEnd)

            const boundsPadded = padLngLatBounds(
                new LngLatBounds(
                    params.boundsStr.split(",").map(Number.parseFloat) as Bounds,
                ),
                0.05,
            )
            console.debug("Search focusing on", boundsPadded)
            map.fitBounds(boundsPadded)
        }

        return () => {
            map.off("moveend", onMapZoomOrMoveEnd)
            removeMapLayer(map, layerId)
            source.setData(emptyFeatureCollection)
            clearMapHover(map, layerId)
            focusObjects(map)
            results = null
            setHover = null
        }
    })

    const controller: IndexController = {
        load: (options) => {
            // Load image resources
            loadMapImage(map, "marker-red", markerRedImageUrl)

            // Stick the search form
            searchForm.classList.add("sticky-top")
            searchAlert.classList.add("d-none")
            searchAlert.addEventListener("click", onSearchAlertClick, { once: true })
            map.off("moveend", onMapZoomOrMoveEnd)

            const searchParams = qsParse(window.location.search)
            const query = searchParams.q || searchParams.query || ""
            const lon = options?.lon ?? searchParams.lon
            const lat = options?.lat ?? searchParams.lat

            if (!query && lon && lat) {
                setPageTitle(whereIsThisTitle)
                setSearchFormQuery(null)

                const zoom = (
                    Number(options?.zoom ?? searchParams.zoom ?? map.getZoom()) | 0
                ).toString()
                base.load(`/partial/where-is-this?${qsEncode({ lon, lat, zoom })}`)
            } else {
                setPageTitle(query || searchTitle)
                setSearchFormQuery(query)

                // Load empty sidebar to ensure proper bbox
                base.load()

                // Pad the bounds to avoid floating point errors
                const [[minLon, minLat], [maxLon, maxLat]] = padLngLatBounds(
                    map.getBounds().adjustAntiMeridian(),
                    -0.01,
                ).toArray()

                base.load(
                    `/partial/search?${qsEncode({
                        q: query,
                        bbox: `${minLon},${minLat},${maxLon},${maxLat}`,
                        local_only: Boolean(options?.localOnly).toString(),
                    })}`,
                )
            }
        },
        unload: () => {
            // Unstick the search form and reset search alert
            searchForm.classList.remove("sticky-top")
            searchAlert.classList.add("d-none")
            base.unload()
        },
    }
    return controller
}
