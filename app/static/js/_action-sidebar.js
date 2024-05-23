import * as L from "leaflet"
import { routerNavigateStrict } from "./index/_router.js"

const actionSidebars = document.querySelectorAll(".action-sidebar")
const closeButtons = document.querySelectorAll(".action-sidebar .sidebar-close-btn")
const searchForms = document.querySelectorAll(".action-sidebar .search-form")
const routingForms = document.querySelectorAll(".action-sidebar .routing-form")

/**
 * Get the action sidebar with the given class name
 * @param {string} className Class name of the sidebar
 * @returns {HTMLDivElement} Action sidebar
 */
export const getActionSidebar = (className) => document.querySelector(`.action-sidebar.${className}`)

/**
 * Switch the action sidebar with the given class name
 * @param {L.Map} map Leaflet map
 * @param {string} className Class name of the sidebar
 * @returns {void}
 */
export const switchActionSidebar = (map, className) => {
    console.debug("switchActionSidebar", className)

    // Reset all search and routing forms
    for (const searchForm of searchForms) searchForm.reset()
    for (const routingForm of routingForms) routingForm.reset()

    // Toggle all action sidebars
    for (const sidebar of actionSidebars) {
        sidebar.classList.toggle("d-none", !sidebar.classList.contains(className))
    }

    // Invalidate the map size
    map.invalidateSize(false)
}

/**
 * Configure action sidebars
 * @returns {void}
 */
export const configureActionSidebars = () => {
    // On sidebar close button click, navigate to index
    const onCloseButtonClick = () => {
        console.debug("configureActionSidebars", "onCloseButtonClick")
        routerNavigateStrict("/")
    }

    // Listen for events
    for (const sidebarCloseButton of closeButtons) {
        sidebarCloseButton.addEventListener("click", onCloseButtonClick)
    }
}
