import i18next from "i18next"
import * as L from "leaflet"
import { qsEncode } from "../_qs.js"
import { getPageTitle } from "../_title.js"
import { getOverlayLayerById } from "../leaflet/_layers.js"
import { makeBoundsMinimumSize } from "../leaflet/_utils.js"
import { getActionSidebar, switchActionSidebar } from "./_action-sidebar.js"
import { routerNavigateStrict } from "./_router.js"

export const styles = {
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

/**
 * Create a new changesets history controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getChangesetsHistoryController = (map) => {
    const changesetLayer = getOverlayLayerById("changesets")
    const sidebar = getActionSidebar("changesets-history")
    const parentSidebar = sidebar.closest(".sidebar")
    const sidebarTitle = sidebar.querySelector(".sidebar-title").textContent
    const entryTemplate = sidebar.querySelector("template.entry")
    const entryContainer = entryTemplate.parentNode
    const loadingContainer = sidebar.querySelector(".loading")

    let abortController = null

    // Store changesets to allow loading more
    const changesets = []
    let changesetsBBox = ""
    let changesetsFinished = false
    const idSidebarMap = new Map()
    const idLayersMap = new Map()

    const updateSidebar = () => {
        idSidebarMap.clear()

        const fragment = document.createDocumentFragment()
        for (const changeset of changesets) {
            const div = entryTemplate.content.cloneNode(true).children[0]

            // Find elements to populate
            const userContainer = div.querySelector(".user")
            const dateContainer = div.querySelector(".date")
            const commentValue = div.querySelector(".comment")
            const changesetAnchor = div.querySelector("a.stretched-link")
            const numCommentsValue = div.querySelector(".num-comments")

            // Populate elements
            if (changeset.user_name) {
                const anchor = document.createElement("a")
                anchor.href = `/user/${changeset.user_name}`
                const img = document.createElement("img")
                img.classList.add("avatar")
                img.src = changeset.user_avatar
                img.alt = i18next.t("alt.profile_picture")
                img.loading = "lazy"
                anchor.appendChild(img)
                anchor.appendChild(document.createTextNode(changeset.user_name))
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
            icon.classList.add("bi", changeset.num_comments ? "bi-chat-left-text" : "bi-chat-left")
            numCommentsValue.classList.toggle("no-comments", !changeset.num_comments)
            numCommentsValue.appendChild(document.createTextNode(changeset.num_comments))
            numCommentsValue.appendChild(icon)

            changesetAnchor.href = `/changeset/${changeset.id}`
            changesetAnchor.textContent = changeset.id
            changesetAnchor.changesetId = changeset.id
            changesetAnchor.addEventListener("mouseover", onMouseover)
            changesetAnchor.addEventListener("mouseout", onMouseout)
            fragment.appendChild(div)

            idSidebarMap.set(changeset.id, div)
        }
        entryContainer.innerHTML = ""
        entryContainer.appendChild(fragment)
    }

    const updateLayers = () => {
        idLayersMap.clear()

        // Sort by bounds area (descending)
        const changesetsSorted = []
        for (const changeset of changesets) {
            const changesetLayers = []
            idLayersMap.set(changeset.id, changesetLayers)
            for (const bounds of changeset.geom) {
                const minimumBounds = makeBoundsMinimumSize(map, bounds)
                const boundsArea = (minimumBounds[2] - minimumBounds[0]) * (minimumBounds[3] - minimumBounds[1])
                changesetsSorted.push([changeset, changesetLayers, minimumBounds, boundsArea])
            }
        }
        changesetsSorted.sort((a, b) => b[3] - a[3])

        // Create layers
        const layers = []
        for (const [changeset, changesetLayers, bounds] of changesetsSorted) {
            const layer = L.rectangle(
                [
                    [bounds[1], bounds[0]],
                    [bounds[3], bounds[2]],
                ],
                styles.default,
            )
            layer.changesetId = changeset.id
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

    /**
     * On layer click, navigate to the changeset
     * @param {L.LeafletMouseEvent} event
     * @returns {void}
     */
    const onLayerClick = (event) => {
        const layer = event.target
        const changesetId = layer.changesetId
        routerNavigateStrict(`/changeset/${changesetId}`)
    }

    /**
     * On mouseover, scroll result into view and focus the changeset
     * @param {MouseEvent} event
     * @returns {void}
     */
    const onMouseover = (event) => {
        const changesetId = event.target.changesetId
        const result = idSidebarMap.get(changesetId)

        const sidebarRect = parentSidebar.getBoundingClientRect()
        const resultRect = result.getBoundingClientRect()
        const isVisible = resultRect.top >= sidebarRect.top && resultRect.bottom <= sidebarRect.bottom
        if (!isVisible) result.scrollIntoView({ behavior: "smooth", block: "center" })

        result.classList.add("hover")
        const layers = idLayersMap.get(changesetId)
        for (const layer of layers) layer.setStyle(styles.hover)
    }

    /**
     * On mouseout, unfocus the changeset
     * @param {MouseEvent} event
     * @returns {void}
     */
    const onMouseout = (event) => {
        const changesetId = event.target.changesetId
        const result = idSidebarMap.get(changesetId)
        result.classList.remove("hover")
        const layers = idLayersMap.get(changesetId)
        for (const layer of layers) layer.setStyle(styles.default)
    }

    /**
     * On sidebar scroll, load more changesets
     * @returns {void}
     */
    const onSidebarScroll = () => {
        if (parentSidebar.offsetHeight + parentSidebar.scrollTop < parentSidebar.scrollHeight) return
        console.debug("Sidebar scrolled to the bottom")
        onMapZoomOrMoveEnd()
    }

    /**
     * On map update, fetch the changesets in view and update the changesets layer
     * @returns {void}
     */
    const onMapZoomOrMoveEnd = () => {
        // Abort any pending request
        if (abortController) abortController.abort()
        abortController = new AbortController()
        const signal = abortController.signal

        const bounds = map.getBounds()
        const minLon = bounds.getWest()
        const minLat = bounds.getSouth()
        const maxLon = bounds.getEast()
        const maxLat = bounds.getNorth()
        const bbox = `${minLon},${minLat},${maxLon},${maxLat}`
        const params = { bbox }

        if (changesetsBBox === bbox && changesets.length) {
            params.before = changesets[changesets.length - 1].id
        } else {
            // Clear the changesets if the bbox changed
            changesetsBBox = bbox
            changesetsFinished = false
            changesets.length = 0
            entryContainer.innerHTML = ""
        }

        if (changesetsFinished) return
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

                const newChangesets = await resp.json()
                changesets.push(...newChangesets)

                if (!newChangesets.length) {
                    console.debug("No more changesets")
                    changesetsFinished = true
                }

                updateSidebar()
                updateLayers()
            })
            .catch((error) => {
                if (error.name === "AbortError") return
                console.error("Failed to fetch map data", error)
                changesetLayer.clearLayers()
                changesetsFinished = false
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
                console.debug("Adding overlay layer", changesetLayer.options.layerId)
                map.addLayer(changesetLayer)
                map.fire("overlayadd", { layer: changesetLayer, name: changesetLayer.options.layerId })
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
                console.debug("Removing overlay layer", changesetLayer.options.layerId)
                map.removeLayer(changesetLayer)
                map.fire("overlayremove", { layer: changesetLayer, name: changesetLayer.options.layerId })
            }

            // Clear the changeset layer
            changesetLayer.clearLayers()
            changesets.length = 0
        },
    }
}
