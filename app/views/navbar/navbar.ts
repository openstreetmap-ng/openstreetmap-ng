import { Collapse, Dropdown, Tooltip } from "bootstrap"
import { routerNavigateStrict } from "../index/_router"
import { encodeMapState, type LonLatZoom, type MapState } from "../lib/map/map-utils"
import { qsParse } from "../lib/qs"
import { remoteEdit } from "../lib/remote-edit"
import type { OSMObject } from "../lib/types"
import { isHrefCurrentPage, wrapMessageEventValidator } from "../lib/utils"

const minEditZoom = 13
const navbar = document.querySelector(".navbar")
const navbarCollapseInstance = Collapse.getOrCreateInstance(
    navbar.querySelector(".navbar-collapse"),
    {
        toggle: false,
    },
)

/**
 * Collapse mobile navbar if currently expanded.
 * Improves user experience when navigating to a new page in SPA mode.
 */
export const collapseNavbar = (): void => navbarCollapseInstance.hide()

// Messages badge
const newUnreadMessagesBadge = navbar.querySelector(".new-unread-messages-badge")
const unreadMessagesBadge = navbar.querySelector(".unread-messages-badge")

/** Update the unread messages badge in the navbar */
export const changeUnreadMessagesBadge = (change: number): void => {
    const current =
        Number.parseInt(newUnreadMessagesBadge.textContent.replace(/\D/g, ""), 10) || 0
    const newCount = current + change
    console.debug("Change unread message badge count", current, "->", newCount)
    newUnreadMessagesBadge.textContent = newCount > 0 ? newCount.toString() : ""
    unreadMessagesBadge.textContent = newCount.toString()
}

// Initialize active nav link
const navLinks = navbar.querySelectorAll("a.nav-link")
for (const link of navLinks) {
    if (isHrefCurrentPage(link.href)) {
        link.classList.add("active")
        link.ariaCurrent = "page"
        break
    }
}

const editGroup = navbar.querySelector("div.edit-group")
const editDropdown = Dropdown.getOrCreateInstance(
    editGroup.querySelector(".dropdown-toggle"),
)
const remoteEditButton = editGroup.querySelector(
    "button.dropdown-item.edit-link[data-editor=remote]",
)
const rememberChoice = editGroup.querySelector("input[name=remember-choice]")

// On edit link click, check and handle the remember choice checkbox
editGroup.addEventListener("click", (event: Event): void => {
    const target = event.target as HTMLElement
    const editLink = target.closest<HTMLAnchorElement | HTMLButtonElement>(".edit-link")
    if (!editLink) return
    const editor = editLink.dataset.editor

    // Without remember choice, continue as usual
    if (!rememberChoice.checked) {
        editDropdown.hide()
        if (editor === "remote" && editLink instanceof HTMLButtonElement)
            remoteEdit(editLink)
        return
    }

    // With remember choice, change default editor first
    event.preventDefault()
    console.debug("Changing default editor to", editor)
    editDropdown.hide()

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
})
// On dropdown hidden, uncheck remember choice checkbox
editGroup.addEventListener("hidden.bs.dropdown", () => {
    if (!rememberChoice.checked) return
    rememberChoice.checked = false
    rememberChoice.dispatchEvent(new Event("change"))
})

// Map of navbar elements to their base href
const mapLinkHrefMap = new Map<HTMLAnchorElement | HTMLButtonElement, string>()
const mapLinks = navbar.querySelectorAll(".map-link") as NodeListOf<
    HTMLAnchorElement | HTMLButtonElement
>
for (const link of mapLinks) {
    mapLinkHrefMap.set(link, link instanceof HTMLAnchorElement ? link.href : "")
}

// TODO: wth object support?
/** Update the navbar links and current URL hash */
export const updateNavbarAndHash = (state: MapState, object?: OSMObject): void => {
    const hash = encodeMapState(state)
    const isEditDisabled = state.zoom < minEditZoom

    for (const [link, baseHref] of mapLinkHrefMap) {
        const isEditLink = link.classList.contains("edit-link")
        if (!isEditLink) {
            if (!(link instanceof HTMLAnchorElement)) {
                console.error(
                    "Expected .map-link that is not .edit-link to be HTMLAnchorElement",
                    link,
                )
                continue
            }
            link.href = baseHref + hash
            continue
        }

        if (link === remoteEditButton) {
            // Remote edit button stores information in dataset
            link.dataset.remoteEdit = JSON.stringify({ state, object })
        } else if (!(link instanceof HTMLAnchorElement)) {
            console.error(
                "Expected .map-link that is .edit-link to be HTMLAnchorElement",
                link,
            )
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
        } else if (link.classList.contains("disabled")) {
            link.classList.remove("disabled")
            link.ariaDisabled = "false"
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
    } else if (editGroup.classList.contains("disabled")) {
        editGroup.classList.remove("disabled")
        editGroup.ariaDisabled = "false"
        const tooltip = Tooltip.getInstance(editGroup)
        tooltip.disable()
        tooltip.hide()
    }

    window.history.replaceState(null, "", hash)
}

/**
 * Handle remote edit path (/edit?editor=remote).
 * Simulate a click on the remote edit button and navigate back to index.
 */
export const handleEditRemotePath = (): void => {
    if (window.location.pathname !== "/edit") return

    const searchParams = qsParse(window.location.search)
    if (searchParams.editor !== "remote") return

    console.debug("handleEditRemotePath")
    routerNavigateStrict("/")
    remoteEditButton.click()
}

// Handle mapState window messages (from iD/Rapid)
window.addEventListener(
    "message",
    wrapMessageEventValidator(({ data }: MessageEvent): void => {
        if (data.type !== "mapState") return
        const { lon, lat, zoom } = data.state as LonLatZoom
        updateNavbarAndHash({ lon, lat, zoom, layersCode: "" })
    }),
)
