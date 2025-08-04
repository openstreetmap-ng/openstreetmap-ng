import { fromBinary } from "@bufbuild/protobuf"
import type { GeoJsonProperties } from "geojson"
import i18next, { t } from "i18next"
import {
    type GeoJSONSource,
    LngLatBounds,
    type MapGeoJSONFeature,
    type Map as MaplibreMap,
} from "maplibre-gl"
import { resolveDatetimeLazy } from "../lib/datetime"
import { clearMapHover, setMapHover } from "../lib/map/hover"
import {
    addMapLayer,
    emptyFeatureCollection,
    getExtendedLayerId,
    type LayerId,
    layersConfig,
    removeMapLayer,
} from "../lib/map/layers/layers.ts"
import {
    convertRenderChangesetsData,
    renderObjects,
} from "../lib/map/render-objects.ts"
import {
    getLngLatBoundsIntersection,
    getLngLatBoundsSize,
    lngLatBoundsEqual,
    makeBoundsMinimumSize,
    padLngLatBounds,
} from "../lib/map/utils"
import {
    type RenderChangesetsData_Changeset,
    RenderChangesetsDataSchema,
} from "../lib/proto/shared_pb"
import { qsEncode, qsParse } from "../lib/qs"
import { setPageTitle } from "../lib/title"
import type { OSMChangeset } from "../lib/types"
import { darkenColor, throttle } from "../lib/utils"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar"
import type { IndexController } from "./_router"
import { routerNavigateStrict } from "./_router"

const fadeSpeed = 0.2
const thicknessSpeed = fadeSpeed * 0.3
const nonInteractiveMaxOpacity = 0.95
const lineWidth = 3
const nonInteractiveLineWidth = lineWidth - 1.5

const layerId = "changesets-history" as LayerId
const layerIdBorders = "changesets-history-borders" as LayerId

layersConfig.set(layerIdBorders, {
    specification: {
        type: "geojson",
        data: emptyFeatureCollection,
    },
    layerTypes: ["line"],
    layerOptions: {
        layout: {
            "line-cap": "round",
            "line-join": "round",
        },
        paint: {
            "line-color": "#fff",
            "line-opacity": 1,
            "line-width": [
                "case",
                ["boolean", ["feature-state", "hover"], false],
                ["feature-state", "scrollBorderWidthHover"],
                ["feature-state", "scrollBorderWidth"],
            ],
        },
    },
    priority: 120,
})

layersConfig.set(layerId, {
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
            "fill-opacity": [
                "case",
                ["boolean", ["feature-state", "hover"], false],
                0.3,
                0,
            ],
            "fill-color": "#ffc",
            "line-color": [
                "case",
                ["boolean", ["feature-state", "hover"], false],
                ["feature-state", "scrollColorHover"],
                ["feature-state", "scrollColor"],
            ],
            "line-opacity": [
                "case",
                ["boolean", ["feature-state", "hover"], false],
                ["feature-state", "scrollOpacityHover"],
                ["feature-state", "scrollOpacity"],
            ],
            "line-width": [
                "case",
                ["boolean", ["feature-state", "hover"], false],
                ["feature-state", "scrollWidthHover"],
                ["feature-state", "scrollWidth"],
            ],
        },
    },
    priority: 121,
})

const loadMoreScrollBuffer = 200
const reloadProportionThreshold = 0.9

/** Create a new changesets history controller */
export const getChangesetsHistoryController = (map: MaplibreMap): IndexController => {
    const source = map.getSource(layerId) as GeoJSONSource
    const sourceBorders = map.getSource(layerIdBorders) as GeoJSONSource
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
    let fetchedDate: string | undefined
    let noMoreChangesets = false
    let loadScope: string | undefined
    let loadDisplayName: string | undefined
    const idChangesetMap = new Map<string, RenderChangesetsData_Changeset>()
    const idFirstFeatureIdMap = new Map<string, number>()
    const idSidebarMap = new Map<string, HTMLElement>()
    let hiddenBefore = 0
    let hiddenAfter = 0

    /** Update changeset visibility states */
    const updateLayersVisibility = (): void => {
        if (!parentSidebar) return

        const sidebarRect = parentSidebar.getBoundingClientRect()
        const sidebarTop = sidebarRect.top
        const sidebarBottom = sidebarRect.bottom

        let newHiddenBefore = 0
        let newHiddenAfter = 0
        let foundVisible = false

        for (let i = changesets.length - 1; i >= 0; i--) {
            const changeset = changesets[i]
            const changesetId = changeset.id.toString()
            const element = idSidebarMap.get(changesetId)
            const elementRect = element.getBoundingClientRect()
            const elementTop = elementRect.top
            const elementBottom = elementRect.bottom

            let state: "above" | "visible" | "below"
            let distance = 0
            let hidden = false

            if (elementBottom < sidebarTop) {
                state = "above"
                distance = (sidebarTop - elementBottom) / sidebarRect.height
            } else if (elementTop > sidebarBottom) {
                state = "below"
                distance = (elementTop - sidebarBottom) / sidebarRect.height
            } else {
                state = "visible"
                distance = 0
            }

            if (state !== "visible") {
                const opacity = nonInteractiveOpacity(distance)
                hidden = opacity < 0.05
            }

            if (!foundVisible && hidden) {
                newHiddenAfter++
            } else if (!hidden) {
                foundVisible = true
            } else if (foundVisible && hidden) {
                newHiddenBefore = i + 1
                break
            }

            if (!hidden) updateFeatureState(changesetId, state, distance)
        }

        if (newHiddenBefore !== hiddenBefore || newHiddenAfter !== hiddenAfter) {
            hiddenBefore = newHiddenBefore
            hiddenAfter = newHiddenAfter
            updateLayers()
        }
    }

    const throttledUpdateLayersVisibility = throttle(updateLayersVisibility, 33)

    /** Calculate non-interactive opacity based on distance */
    const nonInteractiveOpacity = (distance: number): number =>
        Math.max(1 - distance * fadeSpeed, 0) * nonInteractiveMaxOpacity

    /** Update changeset visibility and calculate consecutive hidden ranges */
    const updateFeatureState = (
        changesetId: string,
        state: "above" | "visible" | "below",
        distance: number,
    ): void => {
        const firstFeatureId = idFirstFeatureIdMap.get(changesetId)
        if (firstFeatureId === undefined) return

        const changeset = idChangesetMap.get(changesetId)
        const numBounds = changeset.bounds.length

        let color: string
        let colorHover: string
        let opacity: number
        let opacityHover: number
        let width: number
        let widthHover: number
        let borderWidth: number
        let borderWidthHover: number

        if (state === "visible") {
            color = "#f90"
            colorHover = "#f60"
            opacity = 1
            opacityHover = 1
            width = lineWidth
            widthHover = width + 1.5
            borderWidth = lineWidth + 1.5
            borderWidthHover = borderWidth + 2
        } else {
            color =
                state === "above"
                    ? "#ed59e4" // ~40% lighten
                    : "#14B8A6"
            colorHover = darkenColor(color, 0.15)
            opacity = nonInteractiveOpacity(distance)
            opacityHover = nonInteractiveMaxOpacity
            width = Math.max(
                nonInteractiveLineWidth -
                    distance * thicknessSpeed * nonInteractiveLineWidth,
                0,
            )
            widthHover = Math.max(width, 1) + 1.5
            borderWidth = 0
            borderWidthHover = widthHover + 2
        }

        const featureState = {
            scrollColor: color,
            scrollColorHover: colorHover,
            scrollOpacity: opacity,
            scrollOpacityHover: opacityHover,
            scrollWidth: width,
            scrollWidthHover: widthHover,
            scrollBorderWidth: borderWidth,
            scrollBorderWidthHover: borderWidthHover,
        }

        for (let i = firstFeatureId; i < firstFeatureId + numBounds * 2; i++) {
            map.setFeatureState({ source: layerIdBorders, id: i }, featureState)
            map.setFeatureState({ source: layerId, id: i }, featureState)
        }
    }

    const updateLayers = (e?: any) => {
        const changesetsMinimumSize: OSMChangeset[] = []
        for (const changeset of convertRenderChangesetsData(
            changesets.slice(hiddenBefore, changesets.length - hiddenAfter),
        )) {
            changeset.bounds = changeset.bounds.map((bounds) =>
                makeBoundsMinimumSize(map, bounds),
            )
            changesetsMinimumSize.push(changeset)
        }
        const data = renderObjects(changesetsMinimumSize)
        for (const feature of data.features) {
            idFirstFeatureIdMap.set(
                feature.properties.id,
                feature.properties.firstFeatureId,
            )
        }
        source.setData(data)
        sourceBorders.setData(data)

        // When initial loading for scope/user, focus on the changesets
        if (
            !e &&
            !fetchedBounds &&
            (loadScope || loadDisplayName) &&
            changesets.length
        ) {
            let lngLatBounds: LngLatBounds | null = null
            for (const changeset of changesetsMinimumSize) {
                if (!changeset.bounds.length) continue
                let changesetBounds = new LngLatBounds(changeset.bounds[0])
                for (const bounds of changeset.bounds.slice(1)) {
                    changesetBounds = changesetBounds.extend(bounds)
                }
                lngLatBounds = lngLatBounds
                    ? lngLatBounds.extend(changesetBounds)
                    : changesetBounds
            }
            if (lngLatBounds) {
                console.debug("Fitting map to shown changesets")
                const lngLatBoundsPadded = padLngLatBounds(lngLatBounds, 0.3)
                map.fitBounds(
                    lngLatBoundsPadded,
                    { maxZoom: 16, animate: false },
                    { skipUpdateState: true },
                )
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
            const div = (entryTemplate.content.cloneNode(true) as DocumentFragment)
                .children[0] as HTMLElement

            // Find elements to populate
            const userContainer = div.querySelector(".user")
            const dateContainer = div.querySelector(".date")
            const commentValue = div.querySelector(".comment")
            const changesetLink = div.querySelector("a.stretched-link")
            const numCommentsValue = div.querySelector(".num-comments")
            const statCreateValue = div.querySelector(".stat-create")
            const statModifyValue = div.querySelector(".stat-modify")
            const statDeleteValue = div.querySelector(".stat-delete")

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
                changeset.closed
                    ? i18next.t("browse.closed")
                    : i18next.t("browse.created")
            ).toLowerCase()
            dateContainer.innerHTML += ` ${changeset.timeago}`
            commentValue.textContent =
                changeset.comment || i18next.t("browse.no_comment")

            const icon = document.createElement("i")
            icon.classList.add(
                "bi",
                changeset.numComments ? "bi-chat-left-text" : "bi-chat-left",
            )
            numCommentsValue.classList.toggle("no-comments", !changeset.numComments)
            numCommentsValue.appendChild(
                document.createTextNode(changeset.numComments.toString()),
            )
            numCommentsValue.appendChild(icon)

            if (changeset.numCreate) {
                statCreateValue.textContent = changeset.numCreate.toString()
            } else {
                statCreateValue.remove()
            }
            if (changeset.numModify) {
                statModifyValue.textContent = changeset.numModify.toString()
            } else {
                statModifyValue.remove()
            }
            if (changeset.numDelete) {
                statDeleteValue.textContent = changeset.numDelete.toString()
            } else {
                statDeleteValue.remove()
            }

            changesetLink.href = `/changeset/${changeset.id}`
            changesetLink.textContent = changesetIdStr
            changesetLink.addEventListener("mouseenter", () =>
                setHover(changesetProperties, true),
            )
            changesetLink.addEventListener("mouseleave", () =>
                setHover(changesetProperties, false),
            )
            fragment.appendChild(div)

            idSidebarMap.set(changesetIdStr, div)
        }
        entryContainer.innerHTML = ""
        entryContainer.appendChild(fragment)
        resolveDatetimeLazy(entryContainer)
    }

    /** Set the hover state of the changeset features on interactive layers */
    const setHover = (
        { id, firstFeatureId, numBounds }: GeoJsonProperties,
        hover: boolean,
    ): void => {
        const result = idSidebarMap.get(id)
        result?.classList.toggle("hover", hover)

        for (let i = firstFeatureId; i < firstFeatureId + numBounds * 2; i++) {
            map.setFeatureState({ source: layerIdBorders, id: i }, { hover })
            map.setFeatureState({ source: layerId, id: i }, { hover })
        }
    }

    // On feature click, navigate to the changeset
    const layerIdFill = getExtendedLayerId(layerId, "fill")
    map.on("click", layerIdFill, (e) => {
        // Find feature with the smallest bounds area
        const feature = e.features.reduce((a, b) =>
            a.properties.boundsArea < b.properties.boundsArea ? a : b,
        )
        const changesetId = feature.properties.id
        routerNavigateStrict(`/changeset/${changesetId}`)
    })

    let hoveredFeature: MapGeoJSONFeature | null = null
    map.on("mousemove", layerIdFill, (e) => {
        // Find feature with the smallest bounds area
        const feature = e.features.reduce((a, b) =>
            a.properties.boundsArea < b.properties.boundsArea ? a : b,
        )
        if (hoveredFeature) {
            if (hoveredFeature.id === feature.id) return
            setHover(hoveredFeature.properties, false)
        } else {
            setMapHover(map, layerId)
        }
        hoveredFeature = feature
        setHover(hoveredFeature.properties, true)
    })

    const onMapMouseLeave = () => {
        setHover(hoveredFeature.properties, false)
        hoveredFeature = null
        clearMapHover(map, layerId)
    }
    map.on("mouseleave", layerIdFill, onMapMouseLeave)

    /** On sidebar scroll, update changeset visibility and load more if needed */
    const onSidebarScroll = (): void => {
        // Update changeset visibility based on scroll position
        throttledUpdateLayersVisibility()

        // Load more changesets if scrolled to bottom
        if (
            parentSidebar.offsetHeight + parentSidebar.scrollTop <
            parentSidebar.scrollHeight - loadMoreScrollBuffer
        )
            return
        console.debug("Sidebar scrolled to the bottom")
        updateState()
    }

    /** On map update, fetch the changesets in view and update the changesets layer */
    const updateState = (e?: any): void => {
        if (e?.skipUpdateState) return

        // Request full world when initial loading for scope/user
        const fetchBounds =
            fetchedBounds || (!loadScope && !loadDisplayName) ? map.getBounds() : null

        // During full world view, skip event-based updates
        if (e && !fetchBounds) {
            return
        }

        const params = qsParse(window.location.search)

        // Update date filter element
        const fetchDate = params.date
        dateFilterElement.innerHTML = ""
        if (fetchDate) {
            // Create a span for the text
            const textSpan = document.createElement("span")
            textSpan.textContent = t("changeset.viewing_edits_from_date", {
                date: fetchDate,
            })
            textSpan.classList.add("date-filter-text")
            dateFilterElement.appendChild(textSpan)

            // Create the close button as a link
            const closeLink = document.createElement("a")
            closeLink.href = `${window.location.pathname}?${qsEncode({
                ...params,
                date: undefined,
            })}`
            closeLink.classList.add("btn", "btn-sm", "btn-link", "btn-close")
            closeLink.title = t("action.remove_filter")
            dateFilterElement.appendChild(closeLink)
        }

        if (
            lngLatBoundsEqual(fetchedBounds, fetchBounds) &&
            fetchedDate === fetchDate
        ) {
            // Load more changesets
            if (noMoreChangesets) return
            if (changesets.length)
                params.before = changesets[changesets.length - 1].id.toString()
        } else {
            // Ignore small bounds changes
            if (fetchedBounds && fetchBounds && fetchedDate === fetchDate) {
                const visibleBounds = getLngLatBoundsIntersection(
                    fetchedBounds,
                    fetchBounds,
                )
                const visibleArea = getLngLatBoundsSize(visibleBounds)
                const fetchArea = getLngLatBoundsSize(fetchBounds)
                const proportion =
                    visibleArea /
                    Math.max(getLngLatBoundsSize(fetchedBounds), fetchArea)
                if (proportion > reloadProportionThreshold) return
            }

            // Clear the changesets if the bbox changed
            changesets.length = 0
            idChangesetMap.clear()
            noMoreChangesets = false
            entryContainer.innerHTML = ""
        }
        if (fetchBounds) {
            const [[minLon, minLat], [maxLon, maxLat]] = fetchBounds
                .adjustAntiMeridian()
                .toArray()
            params.bbox = `${minLon},${minLat},${maxLon},${maxLat}`
        }

        params.scope = loadScope
        params.display_name = loadDisplayName

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
                const newChangesets = fromBinary(
                    RenderChangesetsDataSchema,
                    new Uint8Array(buffer),
                ).changesets
                if (newChangesets.length) {
                    changesets.push(...newChangesets)
                    for (const cs of newChangesets) {
                        idChangesetMap.set(cs.id.toString(), cs)
                    }
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
                updateLayersVisibility()
                fetchedBounds = fetchBounds
                fetchedDate = fetchDate
            })
            .catch((error) => {
                if (error.name === "AbortError") return
                console.error("Failed to fetch map data", error)
                source.setData(emptyFeatureCollection)
                sourceBorders.setData(emptyFeatureCollection)
                changesets.length = 0
                idChangesetMap.clear()
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
                sidebarTitleText = t("changesets.index.title_user", {
                    user: displayName,
                })
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

            addMapLayer(map, layerId)
            addMapLayer(map, layerIdBorders)
            map.on("zoomend", updateLayers)
            map.on("moveend", updateState)
            updateState()
        },
        unload: () => {
            if (hoveredFeature) onMapMouseLeave()
            map.off("moveend", updateState)
            map.off("zoomend", updateLayers)
            parentSidebar.removeEventListener("scroll", onSidebarScroll)
            removeMapLayer(map, layerId)
            removeMapLayer(map, layerIdBorders)
            source.setData(emptyFeatureCollection)
            sourceBorders.setData(emptyFeatureCollection)
            changesets.length = 0
            idChangesetMap.clear()
            fetchedBounds = null
            idSidebarMap.clear()
            idFirstFeatureIdMap.clear()
            hiddenBefore = 0
            hiddenAfter = 0
        },
    }
}
