import { Dropdown, Tooltip } from "bootstrap"
import { qsEncode, qsParse } from "./_qs.js"
import { remoteEdit } from "./_remote-edit.js"
import "./_types.js"
import { isHrefCurrentPage } from "./_utils.js"
import { routerNavigateStrict } from "./index/_router.js"
import { encodeMapState } from "./leaflet/_map-utils.js"

const minEditZoom = 13
const navbar = document.querySelector(".navbar")
const editGroup = navbar.querySelector(".edit-group")
const dropdownButton = editGroup.querySelector(".dropdown-toggle")
const dropdown = Dropdown.getOrCreateInstance(dropdownButton)
const dropdownEditButtons = editGroup.querySelectorAll(".dropdown-item.edit-link")
const remoteEditButton = editGroup.querySelector(".dropdown-item.edit-link[data-editor=remote]")
const rememberChoice = editGroup.querySelector("input[name=remember-choice]")
const loginLinks = navbar.querySelectorAll("a[href='/login']")
const newUnreadMessagesBadge = navbar.querySelector(".new-unread-messages-badge")
const unreadMessagesBadge = navbar.querySelector(".unread-messages-badge")

// Add active class to current nav-lik
const navLinks = navbar.querySelectorAll(".nav-link")
for (const link of navLinks) {
    if (isHrefCurrentPage(link.href)) {
        link.classList.add("active")
        link.ariaCurrent = "page"
        break
    }
}

/**
 * Map of navbar elements to their base href
 * @type {Map<HTMLElement, string>}
 */
const mapLinksHrefMap = Array.from(navbar.querySelectorAll(".map-link")).reduce(
    (map, link) => map.set(link, link.href),
    new Map(),
)

/**
 * On edit button click, check and handle the remember choice checkbox
 * @param {PointerEvent} event
 * @returns {void}
 */
const onEditButtonClick = (event) => {
    const editButton = event.currentTarget
    const editor = editButton.dataset.editor

    // Without remember choice, continue as usual
    if (!rememberChoice.checked) {
        dropdown.hide()
        if (editor === "remote") remoteEdit(editButton)
        return
    }

    // With remember choice, change default editor first
    event.preventDefault()
    console.debug("Changing default editor to", editor)
    dropdown.hide()

    const formData = new FormData()
    formData.append("editor", editor)
    fetch("/api/web/settings/editor", {
        method: "POST",
        body: formData,
        mode: "same-origin",
        cache: "no-store",
        priority: "high",
    })
        .then((resp) => {
            if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)
            console.debug("Changed default editor to", editor)
            editButton.dispatchEvent(new MouseEvent(event.type, event))
        })
        .catch((error) => {
            console.error("Failed to change default editor", error)
            alert(error.message)
        })
}
for (const editButton of dropdownEditButtons) {
    editButton.addEventListener("click", onEditButtonClick)
}

// On dropdown hidden, uncheck remember choice checkbox
editGroup.addEventListener("hidden.bs.dropdown", () => {
    if (!rememberChoice.checked) return
    rememberChoice.checked = false
    rememberChoice.dispatchEvent(new Event("change"))
})

/**
 * Update the login links with the current path and hash
 * @param {string} hash Current URL hash
 * @returns {void}
 */
const updateLoginLinks = (hash) => {
    const loginLinkQuery = qsEncode({ referer: window.location.pathname })
    const loginHref = `/login?${loginLinkQuery}${hash}`
    for (const link of loginLinks) link.href = loginHref
}

// TODO: wth object support?
/**
 * Update the navbar links and current URL hash
 * @param {MapState} state Map state object
 * @param {OSMObject|null} object Optional OSM object
 * @returns {void}
 */
export const updateNavbarAndHash = (state, object = null) => {
    const isEditDisabled = state.zoom < minEditZoom
    const hash = encodeMapState(state)
    updateLoginLinks(hash)

    for (const [link, baseHref] of mapLinksHrefMap) {
        const isEditLink = link.classList.contains("edit-link")
        if (isEditLink) {
            if (link === remoteEditButton) {
                // Remote edit button stores information in dataset
                link.dataset.remoteEdit = JSON.stringify({ state, object })
            } else if (object) {
                link.href = `${baseHref}?${object.type}=${object.id}${hash}`
            } else {
                link.href = baseHref + hash
            }

            // Enable/disable edit links based on current zoom level
            if (isEditDisabled) {
                if (!link.classList.contains("disabled")) {
                    link.classList.add("disabled")
                    link.ariaDisabled = "true"
                }
            } else {
                // biome-ignore lint/style/useCollapsedElseIf: Readability
                if (link.classList.contains("disabled")) {
                    link.classList.remove("disabled")
                    link.ariaDisabled = "false"
                }
            }
        } else {
            link.href = baseHref + hash
        }
    }

    // Toggle tooltip on edit group
    if (isEditDisabled) {
        if (!editGroup.classList.contains("disabled")) {
            editGroup.classList.add("disabled")
            editGroup.ariaDisabled = "true"
            Tooltip.getOrCreateInstance(editGroup, {
                title: editGroup.dataset.bsTitle,
                placement: "bottom",
            }).enable()
        }
    } else {
        // biome-ignore lint/style/useCollapsedElseIf: Readability
        if (editGroup.classList.contains("disabled")) {
            editGroup.classList.remove("disabled")
            editGroup.ariaDisabled = "false"
            const tooltip = Tooltip.getInstance(editGroup)
            tooltip.disable()
            tooltip.hide()
        }
    }

    window.history.replaceState(null, "", hash)
}

/**
 * Handle remote edit path (/edit?editor=remote).
 * Simulate a click on the remote edit button and navigate back to index.
 * @returns {void}
 */
export const handleEditRemotePath = () => {
    if (window.location.pathname !== "/edit") return

    const searchParams = qsParse(window.location.search.substring(1))
    if (searchParams.editor !== "remote") return

    console.debug("handleEditRemotePath")
    routerNavigateStrict("/")
    remoteEditButton.click()
}

/**
 * Update the unread messages badge in the navbar
 * @param {number} change Count change
 * @returns {void}
 */
export const changeUnreadMessagesBadge = (change) => {
    const newCount = Number.parseInt(newUnreadMessagesBadge.textContent.replace(/\D/g, "") || 0) + change
    console.debug("changeUnreadMessagesBadge", newCount)
    newUnreadMessagesBadge.textContent = newCount > 0 ? newCount : ""
    unreadMessagesBadge.textContent = newCount
}

// Handle mapState window messages (from iD/Rapid)
addEventListener("message", (event) => {
    const data = event.data
    // On window mapState message, update the navbar and hash
    if (data.type === "mapState") {
        const { lon, lat, zoom } = data.state
        updateNavbarAndHash({ lon, lat, zoom: Math.floor(zoom), layersCode: "" })
    }
})

// Initial update to update the login links
updateLoginLinks(window.location.hash)
