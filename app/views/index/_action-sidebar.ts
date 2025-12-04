import type { Map as MaplibreMap } from "maplibre-gl"
import { collapseNavbar } from "../navbar/navbar"
import { routerNavigateStrict } from "./router"

const actionSidebars = document.querySelectorAll("div.action-sidebar")
const sidebarContainer = actionSidebars.length ? actionSidebars[0].parentElement : null

/** Get the action sidebar with the given class name */
export const getActionSidebar = (className: string): HTMLElement => {
    const sidebar = document.querySelector(`div.action-sidebar.${className}`)
    configureActionSidebar(sidebar)
    return sidebar
}

/** Switch the action sidebar with the given class name */
export const switchActionSidebar = (
    map: MaplibreMap,
    actionSidebar: HTMLElement,
): void => {
    console.debug("switchActionSidebar", actionSidebar.classList)

    // Toggle all action sidebars
    for (const sidebar of actionSidebars) {
        const isTarget = sidebar === actionSidebar
        if (isTarget)
            sidebarContainer.classList.toggle(
                "sidebar-overlay",
                sidebar.dataset.sidebarOverlay === "1",
            )
        sidebar.classList.toggle("d-none", !isTarget)
    }

    map.resize()
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
