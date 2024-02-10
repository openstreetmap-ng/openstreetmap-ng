import { Tooltip } from "bootstrap"
import i18next from "i18next"
import { configureRemoteEditButton } from "./_remote-edit.js"
import "./_types.js"
import { encodeMapState } from "./leaflet/_map-utils.js"

const minEditZoom = 13
const navbar = document.querySelector(".navbar")
const editGroup = navbar.querySelector(".edit-group")

/**
 * Map of navbar elements to their base href
 * @type {Map<HTMLElement, string>}
 */
const mapLinksHrefMap = [...(navbar.querySelectorAll(".map-link") ?? [])].reduce(
    (map, link) => map.set(link, link.getAttribute("href")),
    new Map(),
)

const remoteEditButton = navbar.querySelector(".remote-edit")
if (remoteEditButton) configureRemoteEditButton(remoteEditButton)

/**
 * Update the navbar links and current URL hash
 * @param {MapState} state Map state object
 * @param {OSMObject|null} object Optional OSM object
 * @returns {void}
 */
export const updateNavbarAndHash = (state, object = null) => {
    const isEditDisabled = state.zoom < minEditZoom
    const hash = encodeMapState(state)

    for (const [link, baseHref] of mapLinksHrefMap) {
        const isEditLink = link.classList.contains("edit-link")
        if (isEditLink) {
            // Remote edit button stores information in dataset
            const isRemoteEditButton = link.classList.contains("remote-edit-btn")
            if (isRemoteEditButton) {
                link.dataset.remoteEdit = JSON.stringify({ state, object })
            } else {
                const href = object ? `${baseHref}?${object.type}=${object.id}${hash}` : baseHref + hash
                link.setAttribute("href", href)
            }

            // Enable/disable edit links based on current zoom level
            if (isEditDisabled) {
                if (!link.classList.contains("disabled")) {
                    link.classList.add("disabled")
                    link.setAttribute("aria-disabled", "true")
                }
            } else {
                // biome-ignore lint/style/useCollapsedElseIf: Readability
                if (link.classList.contains("disabled")) {
                    link.classList.remove("disabled")
                    link.setAttribute("aria-disabled", "false")
                }
            }
        } else {
            const href = baseHref + hash
            link.setAttribute("href", href)
        }
    }

    // Toggle tooltip on edit group
    if (isEditDisabled) {
        if (!editGroup.classList.contains("disabled")) {
            editGroup.classList.add("disabled")
            editGroup.setAttribute("aria-disabled", "true")
            Tooltip.getOrCreateInstance(editGroup, {
                title: i18next.t("javascripts.site.edit_disabled_tooltip"),
                placement: "bottom",
            }).enable()
        }
    } else {
        // biome-ignore lint/style/useCollapsedElseIf: Readability
        if (editGroup.classList.contains("disabled")) {
            editGroup.classList.remove("disabled")
            editGroup.setAttribute("aria-disabled", "false")
            Tooltip.getInstance(editGroup).disable()
        }
    }

    history.replaceState(null, "", hash) // TODO: will this not remove path?
}

// On window mapState message, update the navbar and hash
const onMapState = (data) => {
    const { lon, lat, zoom } = data.state
    updateNavbarAndHash({ lon, lat, zoom: Math.floor(zoom), layersCode: "" })
}

addEventListener("message", (event) => {
    const data = event.data
    if (data.type === "mapState") onMapState(data)
})
