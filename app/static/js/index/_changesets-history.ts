import { fromBinary } from "@bufbuild/protobuf"
import i18next from "i18next"
import * as L from "leaflet"
import { resolveDatetime } from "../_datetime"
import { qsEncode } from "../_qs"
import { getPageTitle } from "../_title"
import type { Bounds } from "../_types"
import { type LayerId, getOverlayLayerById } from "../leaflet/_layers"
import { makeBoundsMinimumSize } from "../leaflet/_utils"
import { RenderChangesetsDataSchema, type RenderChangesetsData_Changeset } from "../proto/shared_pb"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar"
import type { IndexController } from "./_router"
import { routerNavigateStrict } from "./_router"

const changesetsLayerId = "changesets" as LayerId

const styles: { [key: string]: L.PolylineOptions } = {
    default: {
        color: "#F90",
        weight: 2,
        opacity: 1,
        fillColor: "#FFC",
        fillOpacity: 0,
    },
    hover: {
        color: "#F60",
        weight: 3,
        fillOpacity: 0.45,
    },
}

/** Create a new changesets history controller */
export const getChangesetsHistoryController = (map: L.Map): IndexController => {
    const changesetLayer = getOverlayLayerById(changesetsLayerId) as L.FeatureGroup
    const sidebar = getActionSidebar("changesets-history")
    const parentSidebar = sidebar.closest("div.sidebar")
    const sidebarTitle = sidebar.querySelector(".sidebar-title").textContent
    const entryTemplate = sidebar.querySelector("template.entry")
    const entryContainer = entryTemplate.parentElement
    const loadingContainer = sidebar.querySelector(".loading")

    let abortController: AbortController | null = null

    // Store changesets to allow loading more
    const changesets: RenderChangesetsData_Changeset[] = []
    let changesetsBBox = ""
    let noMoreChangesets = false
    const idSidebarMap: Map<bigint, HTMLElement> = new Map()
    const idLayersMap: Map<bigint, L.Path[]> = new Map()

    const updateSidebar = (): void => {
        idSidebarMap.clear()

        const fragment = document.createDocumentFragment()
        for (const changeset of changesets) {
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
            changesetLink.textContent = changeset.id.toString()
            ;(changesetLink as any).changesetId = changeset.id
            changesetLink.addEventListener("mouseover", onMouseover)
            changesetLink.addEventListener("mouseout", onMouseout)
            fragment.appendChild(div)

            idSidebarMap.set(changeset.id, div)
        }
        entryContainer.innerHTML = ""
        entryContainer.appendChild(fragment)
        resolveDatetime(entryContainer)
    }

    const updateLayers = () => {
        idLayersMap.clear()

        // Sort by bounds area (descending)
        const changesetsSorted: [RenderChangesetsData_Changeset, L.Path[], Bounds, number][] = []
        for (const changeset of changesets) {
            const changesetLayers: L.Path[] = []
            idLayersMap.set(changeset.id, changesetLayers)
            for (const bounds of changeset.bounds) {
                const { minLon, minLat, maxLon, maxLat } = bounds
                const minimumBounds = makeBoundsMinimumSize(map, [minLon, minLat, maxLon, maxLat])
                const boundsArea = (minimumBounds[2] - minimumBounds[0]) * (minimumBounds[3] - minimumBounds[1])
                changesetsSorted.push([changeset, changesetLayers, minimumBounds, boundsArea])
            }
        }
        changesetsSorted.sort((a, b) => b[3] - a[3])

        // Create layers
        const layers: L.Path[] = []
        for (const [changeset, changesetLayers, bounds] of changesetsSorted) {
            const layer = L.rectangle(
                [
                    [bounds[1], bounds[0]],
                    [bounds[3], bounds[2]],
                ],
                styles.default,
            )
            ;(layer as any).changesetId = changeset.id
            layer.addEventListener("mouseover", onMouseover)
            layer.addEventListener("mouseout", onMouseout)
            layer.addEventListener("click", onLayerClick)
            layers.push(layer)
            changesetLayers.push(layer)
        }

        changesetLayer.clearLayers()
        changesetLayer.addLayer(L.layerGroup(layers))
        console.debug("Changesets layer showing", layers.length, "changesets")
    }

    /** On layer click, navigate to the changeset */
    const onLayerClick = ({ target }: L.LeafletMouseEvent): void => {
        const changesetId: bigint = target.changesetId
        routerNavigateStrict(`/changeset/${changesetId}`)
    }

    /** On mouseover, scroll result into view and focus the changeset */
    const onMouseover = ({ target }: Event | L.LeafletEvent): void => {
        const changesetId: bigint = target.changesetId
        const result = idSidebarMap.get(changesetId)

        const sidebarRect = parentSidebar.getBoundingClientRect()
        const resultRect = result.getBoundingClientRect()
        const isVisible = resultRect.top >= sidebarRect.top && resultRect.bottom <= sidebarRect.bottom
        if (!isVisible) result.scrollIntoView({ behavior: "smooth", block: "center" })

        result.classList.add("hover")
        const layers = idLayersMap.get(changesetId)
        for (const layer of layers) layer.setStyle(styles.hover)
    }

    /** On mouseout, unfocus the changeset */
    const onMouseout = ({ target }: Event | L.LeafletEvent): void => {
        const changesetId: bigint = target.changesetId
        const result = idSidebarMap.get(changesetId)
        result.classList.remove("hover")
        const layers = idLayersMap.get(changesetId)
        for (const layer of layers) layer.setStyle(styles.default)
    }

    /** On sidebar scroll bottom, load more changesets */
    const onSidebarScroll = (): void => {
        if (parentSidebar.offsetHeight + parentSidebar.scrollTop < parentSidebar.scrollHeight) return
        console.debug("Sidebar scrolled to the bottom")
        onMapZoomOrMoveEnd()
    }

    /** On map update, fetch the changesets in view and update the changesets layer */
    const onMapZoomOrMoveEnd = (): void => {
        // Abort any pending request
        abortController?.abort()
        abortController = new AbortController()
        const signal = abortController.signal

        const bounds = map.getBounds()
        const minLon = bounds.getWest()
        const minLat = bounds.getSouth()
        const maxLon = bounds.getEast()
        const maxLat = bounds.getNorth()
        const bbox = `${minLon},${minLat},${maxLon},${maxLat}`
        const params: { [key: string]: string } = { bbox }

        if (changesetsBBox === bbox && changesets.length) {
            params.before = changesets[changesets.length - 1].id.toString()
        } else {
            // Clear the changesets if the bbox changed
            changesetsBBox = bbox
            noMoreChangesets = false
            changesets.length = 0
            entryContainer.innerHTML = ""
        }

        if (noMoreChangesets) return
        loadingContainer.classList.remove("d-none")
        parentSidebar.removeEventListener("scroll", onSidebarScroll)

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
                changesets.push(...newChangesets)

                if (!newChangesets.length) {
                    console.debug("No more changesets")
                    noMoreChangesets = true
                }

                updateSidebar()
                updateLayers()
            })
            .catch((error) => {
                if (error.name === "AbortError") return
                console.error("Failed to fetch map data", error)
                changesetLayer.clearLayers()
                noMoreChangesets = false
                changesets.length = 0
            })
            .finally(() => {
                if (signal.aborted) return
                loadingContainer.classList.add("d-none")
                parentSidebar.addEventListener("scroll", onSidebarScroll)
            })
    }

    return {
        load: () => {
            switchActionSidebar(map, "changesets-history")
            document.title = getPageTitle(sidebarTitle)

            // Create the changeset layer if it doesn't exist
            if (!map.hasLayer(changesetLayer)) {
                console.debug("Adding overlay layer", changesetsLayerId)
                map.addLayer(changesetLayer)
                map.fire("overlayadd", { layer: changesetLayer, name: changesetsLayerId })
            }

            // Listen for events and run initial update
            map.addEventListener("zoomend moveend", onMapZoomOrMoveEnd)
            onMapZoomOrMoveEnd()
        },
        unload: () => {
            map.removeEventListener("zoomend moveend", onMapZoomOrMoveEnd)
            parentSidebar.removeEventListener("scroll", onSidebarScroll)

            // Remove the changeset layer
            if (map.hasLayer(changesetLayer)) {
                console.debug("Removing overlay layer", changesetsLayerId)
                map.removeLayer(changesetLayer)
                map.fire("overlayremove", { layer: changesetLayer, name: changesetsLayerId })
            }

            // Clear the changeset layer
            changesetLayer.clearLayers()
            changesets.length = 0
        },
    }
}
