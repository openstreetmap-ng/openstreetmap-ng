import { fromBinary } from "@bufbuild/protobuf"
import type { GeoJsonProperties } from "geojson"
import i18next, { t } from "i18next"
import { type GeoJSONSource, LngLatBounds, type MapGeoJSONFeature, type Map as MaplibreMap } from "maplibre-gl"
import { resolveDatetimeLazy } from "../_datetime"
import { qsEncode, qsParse } from "../_qs"
import { setPageTitle } from "../_title"
import type { OSMChangeset } from "../_types"
import { clearMapHover, setMapHover } from "../leaflet/_hover.ts"
import {
    type LayerId,
    addMapLayer,
    emptyFeatureCollection,
    getExtendedLayerId,
    layersConfig,
    removeMapLayer,
} from "../leaflet/_layers.ts"
import { convertRenderChangesetsData, renderObjects } from "../leaflet/_render-objects.ts"
import {
    getLngLatBoundsIntersection,
    getLngLatBoundsSize,
    makeBoundsMinimumSize,
    padLngLatBounds,
} from "../leaflet/_utils"
import { RenderChangesetsDataSchema, type RenderChangesetsData_Changeset } from "../proto/shared_pb"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar"
import type { IndexController } from "./_router"
import { routerNavigateStrict } from "./_router"

const layerId = "changesets-history" as LayerId
layersConfig.set(layerId as LayerId, {
    specification: {
        type: "geojson",
        data: emptyFeatureCollection,
    },
    layerTypes: ["fill", "line"],
    layerOptions: {
        layout: {
            "line-cap": "round",
            "line-join": "round",
        },
        paint: {
            "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 0.45, 0],
            "fill-color": "#ffc",
            "line-color": ["case", ["boolean", ["feature-state", "hover"], false], "#f60", "#f90"],
            "line-width": ["case", ["boolean", ["feature-state", "hover"], false], 3, 2],
        },
    },
    priority: 120,
})

const reloadProportionThreshold = 0.9

/** Create a new changesets history controller */
export const getChangesetsHistoryController = (map: MaplibreMap): IndexController => {
    const source = map.getSource(layerId) as GeoJSONSource
    const sidebar = getActionSidebar("changesets-history")
    const parentSidebar = sidebar.closest("div.sidebar")
    const sidebarTitleElement = sidebar.querySelector(".sidebar-title")
    const dateFilterElement = sidebar.querySelector(".date-filter")
    const entryTemplate = sidebar.querySelector("template.entry")
    const entryContainer = entryTemplate.parentElement
    const loadingContainer = sidebar.querySelector(".loading")

    let abortController: AbortController | null = null

    // Store changesets to allow loading more
    const changesets: RenderChangesetsData_Changeset[] = []
    let fetchedBounds: LngLatBounds | null = null
    let noMoreChangesets = false
    let loadScope: string | undefined = undefined
    let loadDisplayName: string | undefined = undefined
    const idFirstFeatureIdMap = new Map<string, number>()
    const idSidebarMap = new Map<string, HTMLElement>()

    const updateLayers = () => {
        const changesetsMinimumSize: OSMChangeset[] = []
        for (const changeset of convertRenderChangesetsData(changesets)) {
            changeset.bounds = changeset.bounds.map((bounds) => makeBoundsMinimumSize(map, bounds))
            changesetsMinimumSize.push(changeset)
        }
        const data = renderObjects(changesetsMinimumSize)
        for (const feature of data.features) {
            idFirstFeatureIdMap.set(feature.properties.id, feature.properties.firstFeatureId)
        }
        source.setData(data)
        console.debug("Changesets layer showing", changesets.length, "changesets")

        // When initial loading for scope/user, focus on the changesets
        if (!fetchedBounds && changesets.length) {
            let lngLatBounds: LngLatBounds | null = null
            for (const changeset of changesetsMinimumSize) {
                if (!changeset.bounds.length) continue
                let changesetBounds = new LngLatBounds(changeset.bounds[0])
                for (const bounds of changeset.bounds.slice(1)) {
                    changesetBounds = changesetBounds.extend(bounds)
                }
                lngLatBounds = lngLatBounds ? lngLatBounds.extend(changesetBounds) : changesetBounds
            }
            if (lngLatBounds) {
                console.debug("Fitting map to shown changesets")
                const lngLatBoundsPadded = padLngLatBounds(lngLatBounds, 0.3)
                map.fitBounds(lngLatBoundsPadded, { maxZoom: 16, animate: false })
            }
        }
    }

    const updateSidebar = (): void => {
        idSidebarMap.clear()

        const fragment = document.createDocumentFragment()
        for (const changeset of changesets) {
            const changesetIdStr = changeset.id.toString()
            const changesetProperties: GeoJsonProperties = {
                id: changesetIdStr,
                firstFeatureId: idFirstFeatureIdMap.get(changesetIdStr),
                numBounds: changeset.bounds.length,
            }
            const div = (entryTemplate.content.cloneNode(true) as DocumentFragment).children[0] as HTMLElement

            // Find elements to populate
            const userContainer = div.querySelector(".user")
            const dateContainer = div.querySelector(".date")
            const commentValue = div.querySelector(".comment")
            const changesetLink = div.querySelector("a.stretched-link")
            const numCommentsValue = div.querySelector(".num-comments")

            // Populate elements
            if (changeset.user) {
                const anchor = document.createElement("a")
                anchor.href = `/user/${changeset.user.name}`
                const img = document.createElement("img")
                img.classList.add("avatar")
                img.src = changeset.user.avatarUrl
                img.alt = i18next.t("alt.profile_picture")
                img.loading = "lazy"
                anchor.appendChild(img)
                anchor.appendChild(document.createTextNode(changeset.user.name))
                userContainer.appendChild(anchor)
            } else {
                userContainer.textContent = i18next.t("browse.anonymous")
            }

            dateContainer.textContent = (
                changeset.closed ? i18next.t("browse.closed") : i18next.t("browse.created")
            ).toLowerCase()
            dateContainer.innerHTML += ` ${changeset.timeago}`
            commentValue.textContent = changeset.comment || i18next.t("browse.no_comment")

            const icon = document.createElement("i")
            icon.classList.add("bi", changeset.numComments ? "bi-chat-left-text" : "bi-chat-left")
            numCommentsValue.classList.toggle("no-comments", !changeset.numComments)
            numCommentsValue.appendChild(document.createTextNode(changeset.numComments.toString()))
            numCommentsValue.appendChild(icon)

            changesetLink.href = `/changeset/${changeset.id}`
            changesetLink.textContent = changesetIdStr
            changesetLink.addEventListener("mouseenter", () => setHover(changesetProperties, true))
            changesetLink.addEventListener("mouseleave", () => setHover(changesetProperties, false))
            fragment.appendChild(div)

            idSidebarMap.set(changesetIdStr, div)
        }
        entryContainer.innerHTML = ""
        entryContainer.appendChild(fragment)
        resolveDatetimeLazy(entryContainer)
    }

    /** Set the hover state of the changeset features */
    const setHover = ({ id, firstFeatureId, numBounds }: GeoJsonProperties, hover: boolean): void => {
        const result = idSidebarMap.get(id)
        result?.classList.toggle("hover", hover)

        if (hover && result) {
            // Scroll result into view
            const sidebarRect = parentSidebar.getBoundingClientRect()
            const resultRect = result.getBoundingClientRect()
            const isVisible = resultRect.top >= sidebarRect.top && resultRect.bottom <= sidebarRect.bottom
            if (!isVisible) result.scrollIntoView({ behavior: "smooth", block: "center" })
        }

        for (let i = firstFeatureId; i < firstFeatureId + numBounds * 2; i++) {
            map.setFeatureState({ source: layerId, id: i }, { hover })
        }
    }

    // On feature click, navigate to the changeset
    const layerIdFill = getExtendedLayerId(layerId, "fill")
    map.on("click", layerIdFill, (e) => {
        // Find feature with the smallest bounds area
        const feature = e.features.reduce((a, b) => (a.properties.boundsArea < b.properties.boundsArea ? a : b))
        const changesetId = feature.properties.id
        routerNavigateStrict(`/changeset/${changesetId}`)
    })

    let hoveredFeature: MapGeoJSONFeature | null = null
    map.on("mouseover", layerIdFill, (e) => {
        // Find feature with the smallest bounds area
        const feature = e.features.reduce((a, b) => (a.properties.boundsArea < b.properties.boundsArea ? a : b))
        if (hoveredFeature) {
            if (hoveredFeature.id === feature.id) return
            setHover(hoveredFeature.properties, false)
        } else {
            setMapHover(map, layerId)
        }
        hoveredFeature = feature
        setHover(hoveredFeature.properties, true)
    })
    map.on("mouseleave", layerIdFill, () => {
        setHover(hoveredFeature.properties, false)
        hoveredFeature = null
        clearMapHover(map, layerId)
    })

    /** On sidebar scroll bottom, load more changesets */
    const onSidebarScroll = (): void => {
        if (parentSidebar.offsetHeight + parentSidebar.scrollTop < parentSidebar.scrollHeight) return
        console.debug("Sidebar scrolled to the bottom")
        updateState()
    }

    /** On map update, fetch the changesets in view and update the changesets layer */
    const updateState = (): void => {
        // Request full world when initial loading for scope/user
        const fetchBounds = fetchedBounds || (!loadScope && !loadDisplayName) ? map.getBounds() : null
        const params = qsParse(location.search.substring(1))
        params.scope = loadScope
        params.display_name = loadDisplayName

        if (fetchedBounds === fetchBounds) {
            // Load more changesets
            if (noMoreChangesets) return
            if (changesets.length) params.before = changesets[changesets.length - 1].id.toString()
        } else {
            // Ignore small bounds changes
            if (fetchedBounds && fetchBounds) {
                const visibleBounds = getLngLatBoundsIntersection(fetchedBounds, fetchBounds)
                const visibleArea = getLngLatBoundsSize(visibleBounds)
                const fetchArea = getLngLatBoundsSize(fetchBounds)
                const proportion = visibleArea / Math.max(getLngLatBoundsSize(fetchedBounds), fetchArea)
                if (proportion > reloadProportionThreshold) return
            }

            // Clear the changesets if the bbox changed
            changesets.length = 0
            noMoreChangesets = false
            entryContainer.innerHTML = ""
        }
        if (fetchBounds) {
            const [[minLon, minLat], [maxLon, maxLat]] = fetchBounds.adjustAntiMeridian().toArray()
            params.bbox = `${minLon},${minLat},${maxLon},${maxLat}`
        }

        loadingContainer.classList.remove("d-none")
        parentSidebar.removeEventListener("scroll", onSidebarScroll)

        // Abort any pending request
        abortController?.abort()
        abortController = new AbortController()
        const signal = abortController.signal

        fetch(`/api/web/changeset/map?${qsEncode(params)}`, {
            method: "GET",
            mode: "same-origin",
            cache: "no-store", // request params are too volatile to cache
            signal: signal,
            priority: "high",
        })
            .then(async (resp) => {
                if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)

                const buffer = await resp.arrayBuffer()
                const newChangesets = fromBinary(RenderChangesetsDataSchema, new Uint8Array(buffer)).changesets
                if (newChangesets.length) {
                    changesets.push(...newChangesets)
                    console.debug(
                        "Changesets layer showing",
                        changesets.length,
                        "changesets, including",
                        newChangesets.length,
                        "new",
                    )
                } else {
                    console.debug("No more changesets")
                    noMoreChangesets = true
                }
                updateLayers()
                updateSidebar()
                fetchedBounds = fetchBounds
            })
            .catch((error) => {
                if (error.name === "AbortError") return
                console.error("Failed to fetch map data", error)
                source.setData(emptyFeatureCollection)
                changesets.length = 0
                noMoreChangesets = false
            })
            .finally(() => {
                if (signal.aborted) return
                loadingContainer.classList.add("d-none")
                parentSidebar.addEventListener("scroll", onSidebarScroll)
            })
    }

    return {
        load: ({ scope, displayName }) => {
            loadScope = scope
            loadDisplayName = displayName

            switchActionSidebar(map, sidebar)
            // TODO: handle scope
            let sidebarTitleHtml: string
            let sidebarTitleText: string
            if (displayName) {
                const userLink = document.createElement("a")
                userLink.href = `/user/${displayName}`
                userLink.textContent = displayName
                sidebarTitleHtml = t("changesets.index.title_user", {
                    user: userLink.outerHTML,
                    interpolation: { escapeValue: false },
                })
                sidebarTitleText = t("changesets.index.title_user", { user: displayName })
            } else if (scope === "nearby") {
                sidebarTitleHtml = t("changesets.index.title_nearby")
                sidebarTitleText = sidebarTitleHtml
            } else if (scope === "friends") {
                sidebarTitleHtml = t("changesets.index.title_friend")
                sidebarTitleText = sidebarTitleHtml
            } else {
                sidebarTitleHtml = t("changesets.index.title")
                sidebarTitleText = sidebarTitleHtml
            }
            sidebarTitleElement.innerHTML = sidebarTitleHtml
            setPageTitle(sidebarTitleText)

            const searchParams = qsParse(location.search.substring(1))

            if (searchParams.date) {
                dateFilterElement.textContent = t("changeset.viewing_edits_from_date", { date: searchParams.date })
            } else {
                dateFilterElement.innerHTML = ""
            }

            addMapLayer(map, layerId)
            map.on("moveend", updateState)
            updateState()
        },
        unload: () => {
            map.off("moveend", updateState)
            parentSidebar.removeEventListener("scroll", onSidebarScroll)
            removeMapLayer(map, layerId)
            source.setData(emptyFeatureCollection)
            clearMapHover(map, layerId)
            changesets.length = 0
            fetchedBounds = null
            idSidebarMap.clear()
            idFirstFeatureIdMap.clear()
        },
    }
}
