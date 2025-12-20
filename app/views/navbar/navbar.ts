import { routerNavigateStrict } from "@index/router"
import { encodeMapState, type LonLatZoom, type MapState } from "@lib/map/state"
import { requestAnimationFramePolyfill } from "@lib/polyfills"
import { qsParse } from "@lib/qs"
import { remoteEdit } from "@lib/remote-edit"
import type { OSMObject } from "@lib/types"
import { isHrefCurrentPage, NON_DIGIT_RE, wrapMessageEventValidator } from "@lib/utils"
import { assert } from "@std/assert"
import { Collapse, Dropdown, Tooltip } from "bootstrap"
import { messagesCountUnread } from "./navbar-right"

const MIN_EDIT_ZOOM = 13
const navbar = document.querySelector(".navbar")!
const navbarCollapseInstance = Collapse.getOrCreateInstance(
    navbar.querySelector(".navbar-collapse")!,
    {
        toggle: false,
    },
)

/**
 * Collapse mobile navbar if currently expanded.
 * Improves user experience when navigating to a new page in SPA mode.
 */
export const collapseNavbar = () => navbarCollapseInstance.hide()

/** Update the unread messages badge in the navbar */
export const changeUnreadMessagesBadge = (change: number) => {
    const oldCount = messagesCountUnread.value
    const newCount = oldCount + change
    console.debug("Navbar: Message badge changed", oldCount, "->", newCount)
    messagesCountUnread.value = newCount
}

// Initialize active nav link
const navLinks = navbar.querySelectorAll("a.nav-link")
const activeNavLink = Array.from(navLinks).find((link) => isHrefCurrentPage(link.href))
if (activeNavLink) {
    activeNavLink.classList.add("active")
    activeNavLink.ariaCurrent = "page"
}

const editGroup = navbar.querySelector("div.edit-group")!
const editDropdown = Dropdown.getOrCreateInstance(
    editGroup.querySelector(".dropdown-toggle")!,
)
const remoteEditButton = editGroup.querySelector(
    "button.dropdown-item.edit-link[data-editor=remote]",
)!
const rememberChoice = editGroup.querySelector("input[name=remember-choice]")!
const editGroupTooltip = Tooltip.getOrCreateInstance(editGroup, {
    title: editGroup.dataset.bsTitle!,
    placement: "bottom",
})
editGroupTooltip.disable()

// On edit link click, check and handle the remember choice checkbox
editGroup.addEventListener("click", async (e) => {
    const target = e.target as HTMLElement
    const editLink = target.closest<HTMLAnchorElement | HTMLButtonElement>(".edit-link")
    if (!editLink) return
    const editor = editLink.dataset.editor!

    // Without remember choice, continue as usual
    if (!rememberChoice.checked) {
        editDropdown.hide()
        if (editor === "remote" && editLink instanceof HTMLButtonElement)
            remoteEdit(editLink)
        return
    }

    // With remember choice, change default editor first
    e.preventDefault()
    console.debug("Navbar: Changing default editor", editor)
    editDropdown.hide()

    const formData = new FormData()
    formData.append("editor", editor)
    try {
        const resp = await fetch("/api/web/settings/editor", {
            method: "POST",
            body: formData,
            priority: "high",
        })
        assert(resp.ok, `${resp.status} ${resp.statusText}`)
        console.debug("Navbar: Default editor changed", editor)
        editLink.dispatchEvent(new MouseEvent(e.type, e))
    } catch (error) {
        console.error("Navbar: Failed to change editor", error)
        alert(error.message)
    }
})
// On dropdown hidden, uncheck remember choice checkbox
editGroup.addEventListener("hidden.bs.dropdown", () => {
    if (!rememberChoice.checked) return
    rememberChoice.checked = false
    rememberChoice.dispatchEvent(new Event("change"))
})

// Cache base href on elements to avoid string munging later
const mapLinks = navbar.querySelectorAll<HTMLAnchorElement | HTMLButtonElement>(
    ".map-link",
)
const editLinks = navbar.querySelectorAll<HTMLAnchorElement | HTMLButtonElement>(
    ".edit-link",
)
for (const link of mapLinks) {
    if (link instanceof HTMLAnchorElement) link.dataset.baseHref = link.href
}

const setEditControlsDisabled = (disabled: boolean) => {
    for (const link of editLinks) {
        link.classList.toggle("disabled", disabled)
        link.ariaDisabled = disabled ? "true" : null
    }
    editGroup.classList.toggle("disabled", disabled)
    editGroup.ariaDisabled = disabled ? "true" : null
    if (disabled) {
        editGroupTooltip.enable()
    } else {
        editGroupTooltip.disable()
        editGroupTooltip.hide()
    }
}

// TODO: wth object support?
/** Update the navbar links and current URL hash */
export const updateNavbarAndHash = (state: MapState, object?: OSMObject) => {
    const hash = encodeMapState(state)
    const isEditDisabled = state.zoom < MIN_EDIT_ZOOM

    for (const link of mapLinks) {
        const isEditLink = link.classList.contains("edit-link")

        if (!isEditLink) {
            if (link instanceof HTMLAnchorElement)
                link.href = link.dataset.baseHref + hash
            continue
        }

        if (link === remoteEditButton) {
            // Remote edit button stores information in dataset
            link.dataset.remoteEdit = JSON.stringify({ state, object })
            continue
        }

        if (link instanceof HTMLAnchorElement) {
            const baseHref = link.dataset.baseHref!
            if (object) {
                const url = new URL(baseHref, window.location.origin)
                url.searchParams.set(object.type, String(object.id))
                link.href = url.pathname + url.search + hash
            } else {
                link.href = baseHref + hash
            }
        } else {
            console.error("Navbar: Expected .edit-link to be HTMLAnchorElement", link)
        }
    }

    setEditControlsDisabled(isEditDisabled)
    window.history.replaceState(null, "", hash)
}

/**
 * Handle remote edit path (/edit?editor=remote).
 * Simulate a click on the remote edit button and navigate back to index.
 */
export const handleEditRemotePath = () => {
    if (window.location.pathname !== "/edit") return

    const searchParams = qsParse(window.location.search)
    if (searchParams.editor !== "remote") return

    console.debug("Navbar: Handle edit remote path")
    routerNavigateStrict("/")
    remoteEditButton.click()
}

// Handle mapState window messages (from iD/Rapid)
window.addEventListener(
    "message",
    wrapMessageEventValidator(({ data }: MessageEvent) => {
        if (data.type !== "mapState") return
        const { lon, lat, zoom } = data.state as LonLatZoom
        updateNavbarAndHash({ lon, lat, zoom, layersCode: "" })
    }),
)

// Responsive navbar links
const navbarLinksList = navbar.querySelector("ul.navbar-nav")
if (navbarLinksList) {
    const navbarLinksParent = navbarLinksList.parentElement!
    const moreDropdown = navbar.querySelector("div.navbar-nav-more")!
    const moreDropdownList = moreDropdown.querySelector("ul")!
    let moreButtonWidth = 80

    const collapseBuffer = 60
    const expandBuffer = 80

    // Check if navbar links overflow and adjust layout
    const _updateNavbarLayoutInner = () => {
        let availableWidth: number
        if (window.innerWidth >= 992) {
            availableWidth = navbarLinksParent.offsetWidth

            // Get other elements width
            for (const child of navbarLinksParent.children) {
                if (child === navbarLinksList || child === moreDropdown) continue
                availableWidth -= (child as HTMLElement).offsetWidth
            }

            // Get "More" button width
            moreButtonWidth = moreDropdown.offsetWidth || moreButtonWidth
            availableWidth -= moreButtonWidth
        } else {
            // Force expand for mobile
            availableWidth = Number.POSITIVE_INFINITY
        }

        let currentWidth = navbarLinksList.scrollWidth

        const shouldCollapse = () =>
            navbarLinksList.children.length &&
            currentWidth + collapseBuffer > availableWidth

        const shouldExpand = () =>
            moreDropdownList.children.length &&
            currentWidth +
                Number.parseFloat(
                    (moreDropdownList.firstElementChild as HTMLLIElement).dataset
                        .width!,
                ) +
                expandBuffer <
                availableWidth

        if (shouldCollapse()) {
            // Get all widths at once to avoid layout thrashing
            const linkWidths = Array.from(
                navbarLinksList.children,
                (child) => (child as HTMLElement).offsetWidth,
            )

            const fragment = document.createDocumentFragment()

            while (shouldCollapse()) {
                const linkItem = navbarLinksList.lastElementChild as HTMLLIElement
                const link = linkItem.firstElementChild as HTMLAnchorElement
                const linkWidth =
                    linkWidths.pop() ?? (linkItem as HTMLElement).offsetWidth
                currentWidth -= linkWidth

                // Create dropdown item
                const dropdownItem = document.createElement("li")
                dropdownItem.dataset.width = linkWidth.toString()

                link.classList.replace("nav-link", "dropdown-item")
                dropdownItem.append(link)

                fragment.prepend(dropdownItem)
                linkItem.remove()
            }

            moreDropdownList.prepend(fragment)
        } else if (shouldExpand()) {
            const fragment = document.createDocumentFragment()

            while (shouldExpand()) {
                const dropdownItem = moreDropdownList.firstElementChild as HTMLLIElement
                const link = dropdownItem.firstElementChild as HTMLAnchorElement
                const linkWidth = Number.parseFloat(dropdownItem.dataset.width!)
                currentWidth += linkWidth

                // Create nav link item
                const linkItem = document.createElement("li")
                linkItem.classList.add("nav-item")

                link.classList.replace("dropdown-item", "nav-link")
                linkItem.append(link)

                fragment.append(linkItem)
                dropdownItem.remove()
            }

            navbarLinksList.append(fragment)
        }

        // Update more button visibility
        moreDropdown.classList.toggle("d-none", !moreDropdownList.children.length)
    }

    let navbarLayoutRaf = 0
    const updateNavbarLayout = () => {
        if (navbarLayoutRaf) return
        navbarLayoutRaf = requestAnimationFramePolyfill(() => {
            navbarLayoutRaf = 0
            _updateNavbarLayoutInner()
        })
    }

    // Setup resize observer
    const resizeObserver = new ResizeObserver(updateNavbarLayout)
    resizeObserver.observe(navbarLinksParent)

    // Initial layout update
    updateNavbarLayout()
}
