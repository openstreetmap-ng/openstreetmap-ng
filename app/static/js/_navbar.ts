import { Dropdown, Tooltip } from "bootstrap"
import { qsEncode, qsParse } from "./_qs"
import { remoteEdit } from "./_remote-edit"
import type { OSMObject } from "./_types"
import { isHrefCurrentPage } from "./_utils"
import { routerNavigateStrict } from "./index/_router"
import { type LonLatZoom, type MapState, encodeMapState } from "./leaflet/_map-utils"

const minEditZoom = 13
const navbar = document.querySelector(".navbar")

// Add active class to current nav-lik
const navLinks = navbar.querySelectorAll("a.nav-link")
for (const link of navLinks) {
    if (isHrefCurrentPage(link.href)) {
        link.classList.add("active")
        link.ariaCurrent = "page"
        break
    }
}

const editGroup = navbar.querySelector("div.edit-group")
const dropdown = Dropdown.getOrCreateInstance(editGroup.querySelector(".dropdown-toggle"))
const editLinks = editGroup.querySelectorAll(".dropdown-item.edit-link") as NodeListOf<
    HTMLAnchorElement | HTMLButtonElement
>
const remoteEditButton = editGroup.querySelector("button.dropdown-item.edit-link[data-editor=remote]")
const rememberChoice = editGroup.querySelector("input[name=remember-choice]")

const mapLinks = navbar.querySelectorAll(".map-link") as NodeListOf<HTMLAnchorElement | HTMLButtonElement>
// Map of navbar elements to their base href
const mapLinksHrefMap: Map<HTMLAnchorElement | HTMLButtonElement, string> = new Map()
for (const link of mapLinks) {
    mapLinksHrefMap.set(link, link instanceof HTMLAnchorElement ? link.href : "")
}

/** On edit link click, check and handle the remember choice checkbox */
const onEditLinkClick = (event: Event): void => {
    const editLink = event.currentTarget as HTMLAnchorElement | HTMLButtonElement
    const editor = editLink.dataset.editor

    // Without remember choice, continue as usual
    if (!rememberChoice.checked) {
        dropdown.hide()
        if (editor === "remote" && editLink instanceof HTMLButtonElement) remoteEdit(editLink)
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
            editLink.dispatchEvent(new MouseEvent(event.type, event))
        })
        .catch((error) => {
            console.error("Failed to change default editor", error)
            alert(error.message)
        })
}
for (const editLink of editLinks) {
    editLink.addEventListener("click", onEditLinkClick)
}

// On dropdown hidden, uncheck remember choice checkbox
editGroup.addEventListener("hidden.bs.dropdown", () => {
    if (!rememberChoice.checked) return
    rememberChoice.checked = false
    rememberChoice.dispatchEvent(new Event("change"))
})

const loginLinks: NodeListOf<HTMLAnchorElement> = navbar.querySelectorAll("a[href='/login']")
/** Update the login links with the current path and hash */
const updateLoginLinks = (hash: string): void => {
    const loginLinkQuery = qsEncode({ referer: window.location.pathname })
    const loginHref = `/login?${loginLinkQuery}${hash}`
    for (const link of loginLinks) link.href = loginHref
}

// TODO: wth object support?
/** Update the navbar links and current URL hash */
export const updateNavbarAndHash = (state: MapState, object?: OSMObject): void => {
    const isEditDisabled = state.zoom < minEditZoom
    const hash = encodeMapState(state)
    updateLoginLinks(hash)

    for (const [link, baseHref] of mapLinksHrefMap) {
        const isEditLink = link.classList.contains("edit-link")
        if (isEditLink) {
            if (link === remoteEditButton) {
                // Remote edit button stores information in dataset
                link.dataset.remoteEdit = JSON.stringify({ state, object })
            } else if (!(link instanceof HTMLAnchorElement)) {
                console.error("Expected .map-link that is .edit-link to be <a> (excluding data-editor=remote)")
                continue
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
            if (!(link instanceof HTMLAnchorElement)) {
                console.error("Expected .map-link that is not .edit-link to be <a>")
                continue
            }
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
 */
export const handleEditRemotePath = (): void => {
    if (window.location.pathname !== "/edit") return

    const searchParams = qsParse(window.location.search.substring(1))
    if (searchParams.editor !== "remote") return

    console.debug("handleEditRemotePath")
    routerNavigateStrict("/")
    remoteEditButton.click()
}

const newUnreadMessagesBadge = navbar.querySelector(".new-unread-messages-badge")
const unreadMessagesBadge = navbar.querySelector(".unread-messages-badge")
/** Update the unread messages badge in the navbar */
export const changeUnreadMessagesBadge = (change: number): void => {
    const newCount = (Number.parseInt(newUnreadMessagesBadge.textContent.replace(/\D/g, "")) || 0) + change
    console.debug("changeUnreadMessagesBadge", newCount)
    newUnreadMessagesBadge.textContent = newCount > 0 ? newCount.toString() : ""
    unreadMessagesBadge.textContent = newCount.toString()
}

// Handle mapState window messages (from iD/Rapid)
window.addEventListener("message", (event: MessageEvent): void => {
    const data = event.data
    if (data.type === "mapState") {
        const { lon, lat, zoom } = data.state as LonLatZoom
        updateNavbarAndHash({ lon, lat, zoom: Math.floor(zoom), layersCode: "" })
    }
})

// Initial update to update the login links
updateLoginLinks(window.location.hash)
