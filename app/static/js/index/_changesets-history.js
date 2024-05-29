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
    const sidebarTitle = sidebar.querySelector(".sidebar-title").textContent
    const entryTemplate = sidebar.querySelector("template.entry")
    const entryContainer = entryTemplate.parentNode
    const spinnerContainer = sidebar.querySelector(".spinner-container")

    let abortController = null

    // Store changesets to allow loading more
    const changesets = []
    let changesetsBBox = ""
    let changesetsFinished = false
    const idSidebarMap = new Map()
    const idLayerMap = new Map()

    const updateSidebar = () => {
        idSidebarMap.clear()

        const fragment = document.createDocumentFragment()
        for (const changeset of changesets) {
            const div = entryTemplate.content.cloneNode(true).children[0]
            div.dataset.changesetId = changeset.id
            div.addEventListener("mouseover", onSidebarMouseover)
            div.addEventListener("mouseout", onSidebarMouseout)

            const userContainer = div.querySelector(".user")
            const dateContainer = div.querySelector(".date")
            const tagValue = div.querySelector(".tag-value")
            const changesetAnchor = div.querySelector("a.changeset-id")
            const commentsContainer = div.querySelector(".comments")

            if (changeset.user_name) {
                const anchor = document.createElement("a")
                anchor.href = `/user/${changeset.user_name}`
                const img = document.createElement("img")
                img.classList.add("avatar")
                img.src = changeset.user_avatar
                img.alt = i18next.t("user.profile_picture")
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
            tagValue.textContent = changeset.comment || i18next.t("browse.no_comment")

            const icon = document.createElement("i")
            icon.classList.add("bi", changeset.num_comments ? "bi-chat-left-text" : "bi-chat-left")
            commentsContainer.classList.toggle("no-comments", !changeset.num_comments)
            commentsContainer.appendChild(document.createTextNode(changeset.num_comments))
            commentsContainer.appendChild(icon)

            changesetAnchor.href = `/changeset/${changeset.id}`
            changesetAnchor.textContent = changeset.id
            fragment.appendChild(div)

            idSidebarMap.set(changeset.id, div)
        }
        entryContainer.innerHTML = ""
        entryContainer.appendChild(fragment)
    }

    const updateLayers = () => {
        idLayerMap.clear()

        // Sort by bounds area (descending)
        const changesetsSorted = []
        for (const changeset of changesets) {
            const bounds = makeBoundsMinimumSize(map, changeset.geom)
            const boundsArea = (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])
            changesetsSorted.push([changeset, bounds, boundsArea])
        }
        changesetsSorted.sort((a, b) => b[2] - a[2])

        // Create layers
        const layers = []
        for (const [changeset, bounds] of changesetsSorted) {
            const geom = [
                [bounds[1], bounds[0]],
                [bounds[3], bounds[2]],
            ]
            const layer = L.rectangle(geom, styles.default)
            layer.changesetId = changeset.id
            layer.addEventListener("mouseover", onLayerMouseover)
            layer.addEventListener("mouseout", onLayerMouseout)
            layer.addEventListener("click", onLayerClick)
            layers.push(layer)

            idLayerMap.set(changeset.id, layer)
        }

        changesetLayer.clearLayers()
        if (layers.length) changesetLayer.addLayer(L.layerGroup(layers))
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
     * On layer mouseover, highlight the changeset
     * @param {L.LeafletMouseEvent} event
     * @returns {void}
     */
    const onLayerMouseover = (event) => {
        const layer = event.target
        layer.setStyle(styles.hover)
        idSidebarMap.get(layer.changesetId).classList.add("hover")
    }

    /**
     * On layer mouseout, un-highlight the changeset
     * @param {L.LeafletMouseEvent} event
     * @returns {void}
     */
    const onLayerMouseout = (event) => {
        const layer = event.target
        layer.setStyle(styles.default)
        idSidebarMap.get(layer.changesetId).classList.remove("hover")
    }

    /**
     * On sidebar mouseover, highlight the changeset layer
     * @param {MouseEvent} event
     * @returns {void}
     */
    const onSidebarMouseover = (event) => {
        const div = event.target.closest(".result-action")
        const changesetId = Number.parseInt(div.dataset.changesetId)
        const layer = idLayerMap.get(changesetId)
        layer.setStyle(styles.hover)
    }

    /**
     * On sidebar mouseout, un-highlight the changeset layer
     * @param {MouseEvent} event
     * @returns {void}
     */
    const onSidebarMouseout = (event) => {
        const div = event.target.closest(".result-action")
        const changesetId = Number.parseInt(div.dataset.changesetId)
        const layer = idLayerMap.get(changesetId)
        layer.setStyle(styles.default)
    }

    /**
     * On sidebar scroll, load more changesets
     * @returns {void}
     */
    const onSidebarScroll = () => {
        if (sidebar.offsetHeight + sidebar.scrollTop < sidebar.scrollHeight) return
        console.debug("Sidebar scrolled to bottom")
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
        spinnerContainer.classList.remove("d-none")
        sidebar.removeEventListener("scroll", onSidebarScroll)

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
                spinnerContainer.classList.add("d-none")
                sidebar.addEventListener("scroll", onSidebarScroll)
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
