import * as L from "leaflet"
import { getTagsDiffMode, setTagsDiffMode } from "../_local-storage"
import { qsEncode, qsParse } from "../_qs"
import { getPageTitle } from "../_title"
import { focusManyMapObjects, focusMapObject } from "../leaflet/_focus-layer"
import { getBaseFetchController } from "./_base-fetch"
import { initializeElementContent } from "./_element"

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

        // Set page title
        document.title = getPageTitle(sidebarTitle)

        // Handle not found
        if (!sidebarTitleElement.dataset.params) return

        // Get params
        const params = JSON.parse(sidebarTitleElement.dataset.params)
        const paramsType = params.type
        const paramsId = params.id

        const tagsDiffCheckbox = sidebarContent.querySelector(".tags-diff-mode")
        tagsDiffCheckbox.checked = getTagsDiffMode()
        tagsDiffCheckbox.addEventListener("change", () => {
            setTagsDiffMode(tagsDiffCheckbox.checked)
            base.unload()
            base.load({ type: paramsType, id: paramsId })
        })

        const versionSections = sidebarContent.querySelectorAll(".version-section")
        for (const versionSection of versionSections) {
            const elements = initializeElementContent(map, versionSection)
            versionSection.addEventListener("mouseenter", () => focusManyMapObjects(map, elements)) // focus elements
            versionSection.addEventListener("mouseleave", () => focusMapObject(map, null)) // remove focus
        }

        const paginationContainer = sidebarContent.querySelector(".history-pagination")
        if (paginationContainer) {
            const dataset = paginationContainer.dataset
            const currentPage = Number.parseInt(dataset.page, 10)
            const totalPages = Number.parseInt(dataset.numPages, 10)
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

                const anchor = document.createElement("a")
                anchor.classList.add("page-link")
                anchor.textContent = i
                anchor.href = `?page=${i}`
                if (distance === 1) anchor.rel = i < currentPage ? "prev" : "next"

                li.appendChild(anchor)

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
        const params = qsParse(location.search.substring(1))
        params.tags_diff_mode = getTagsDiffMode()
        const url = `/api/partial/${type}/${id}/history?${qsEncode(params)}`
        baseLoad({ url })
    }

    base.unload = () => {
        focusMapObject(map, null)
        baseUnload()
    }

    return base
}
