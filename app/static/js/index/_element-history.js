import * as L from "leaflet"
import { getPageTitle } from "../_title.js"
import { focusManyMapObjects, focusMapObject } from "../leaflet/_focus-layer-util.js"
import { getBaseFetchController } from "./_base-fetch.js"
import { initializeElementContent } from "./_element.js"
import { routerNavigateStrict } from "./_router.js"

const paginationDistance = 2

/**
 * Create a new element history controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getElementHistoryController = (map) => {
    const onLoaded = (sidebarContent) => {
        // Get elements
        const sidebarTitleElement = sidebarContent.querySelector(".sidebar-title")
        const sidebarTitle = sidebarTitleElement.textContent
        const paginationContainer = sidebarContent.querySelector(".history-pagination")

        // Set page title
        document.title = getPageTitle(sidebarTitle)

        // TODO: Handle not found
        // if (!sidebarTitleElement.dataset.params) return

        const versionSections = sidebarContent.querySelectorAll(".version-section")
        const versionElements = []

        for (const versionSection of versionSections) {
            const elements = initializeElementContent(map, versionSection)
            versionElements.push(elements)

            // On mouse enter, focus elements
            const onVersionMouseEnter = () => {
                console.debug("onVersionMouseEnter")
                focusManyMapObjects(map, elements)
            }

            // On mouse leave, remove focus
            const onVersionMouseLeave = () => {
                console.debug("onVersionMouseLeave")
                focusMapObject(map, null)
            }

            // On click, navigate to version
            const onVersionClick = (e) => {
                const target = e.target
                if (target.closest("a, button, details")) return

                console.debug("onVersionClick")
                const { type, id, version } = JSON.parse(versionSection.dataset.params)
                const path = `/${type}/${id}/history/${version}`
                routerNavigateStrict(path)
            }

            // Listen for events
            versionSection.addEventListener("mouseenter", onVersionMouseEnter)
            versionSection.addEventListener("mouseleave", onVersionMouseLeave)
            versionSection.addEventListener("click", onVersionClick)
        }

        if (paginationContainer) {
            const dataset = paginationContainer.dataset
            const currentPage = parseInt(dataset.page)
            const totalPages = parseInt(dataset.numPages)
            console.debug("Initializing element history pagination", dataset)

            const paginationFragment = document.createDocumentFragment()

            for (let i = 1; i <= totalPages; i++) {
                const distance = Math.abs(i - currentPage)
                if (distance > paginationDistance && i !== 1 && i !== totalPages) {
                    if (i === 2 || i === totalPages - 1) {
                        const li = document.createElement("li")
                        li.classList.add("page-item", "disabled")
                        li.ariaDisabled = "true"
                        li.innerHTML = `<span class="page-link">...</span>`
                        paginationFragment.appendChild(li)
                    }
                    continue
                }

                const li = document.createElement("li")
                li.classList.add("page-item")

                const button = document.createElement("a")
                button.classList.add("page-link")
                button.textContent = i
                button.href = `?page=${i}`
                li.appendChild(button)

                if (i === currentPage) {
                    li.classList.add("active")
                    li.ariaCurrent = "page"
                }

                paginationFragment.appendChild(li)
            }

            paginationContainer.appendChild(paginationFragment)
        }
    }

    const base = getBaseFetchController(map, "element-history", onLoaded)
    const baseLoad = base.load
    const baseUnload = base.unload

    base.load = ({ type, id }) => {
        const url = `/api/partial/element/${type}/${id}/history${location.search}`
        baseLoad({ url })
    }

    base.unload = () => {
        focusMapObject(map, null)
        baseUnload()
    }

    return base
}
