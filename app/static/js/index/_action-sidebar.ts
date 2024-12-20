import type * as L from "leaflet"
import { collapseNavbar } from "../_navbar"
import { routerNavigateStrict } from "./_router"

const actionSidebars = document.querySelectorAll("div.action-sidebar")
const sidebarContainer = actionSidebars.length ? actionSidebars[0].parentElement : null

/** Get the action sidebar with the given class name */
export const getActionSidebar = (className: string): HTMLElement => {
    const sidebar = document.querySelector(`div.action-sidebar.${className}`)
    configureActionSidebar(sidebar)
    return sidebar
}

/** Switch the action sidebar with the given class name */
export const switchActionSidebar = (map: L.Map, className: string): void => {
    console.debug("switchActionSidebar", className)

    // Toggle all action sidebars
    for (const sidebar of actionSidebars) {
        const isTarget = sidebar.classList.contains(className)
        if (isTarget) sidebarContainer.classList.toggle("sidebar-overlay", sidebar.dataset.sidebarOverlay === "1")
        sidebar.classList.toggle("d-none", !isTarget)
    }

    // Invalidate the map size
    map.invalidateSize(false)
    collapseNavbar()
}

/** On sidebar close button click, navigate to index */
const onCloseButtonClick = () => {
    console.debug("configureActionSidebar", "onCloseButtonClick")
    routerNavigateStrict("/")
}

/** Configure action sidebar events */
export const configureActionSidebar = (sidebar: Element): void => {
    const closeButton = sidebar.querySelector(".sidebar-close-btn")
    closeButton?.addEventListener("click", onCloseButtonClick)
}
