import * as L from "leaflet"
import { routerNavigateStrict } from "./_router"

const actionSidebars = document.querySelectorAll(".action-sidebar")
const sidebarContainer = actionSidebars.length ? actionSidebars[0].parentElement : null

/**
 * Get the action sidebar with the given class name
 * @param {string} className Class name of the sidebar
 * @returns {HTMLDivElement} Action sidebar
 */
export const getActionSidebar = (className) => {
    const sidebar = document.querySelector(`.action-sidebar.${className}`)
    configureActionSidebar(sidebar)
    return sidebar
}

/**
 * Switch the action sidebar with the given class name
 * @param {L.Map} map Leaflet map
 * @param {string} className Class name of the sidebar
 * @returns {void}
 */
export const switchActionSidebar = (map, className) => {
    console.debug("switchActionSidebar", className)

    // Toggle all action sidebars
    for (const sidebar of actionSidebars) {
        const isTarget = sidebar.classList.contains(className)
        if (isTarget) sidebarContainer.classList.toggle("sidebar-overlay", sidebar.dataset.sidebarOverlay === "1")
        sidebar.classList.toggle("d-none", !isTarget)
    }

    // Invalidate the map size
    map.invalidateSize(false)
}

// On sidebar close button click, navigate to index
const onCloseButtonClick = () => {
    console.debug("configureActionSidebars", "onCloseButtonClick")
    routerNavigateStrict("/")
}

/**
 * Configure action sidebars
 * @returns {void}
 */
export const configureActionSidebar = (sidebar) => {
    // Listen for events
    const closeButton = sidebar.querySelector(".sidebar-close-btn")
    if (closeButton) closeButton.addEventListener("click", onCloseButtonClick)
}
