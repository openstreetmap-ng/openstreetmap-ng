import type * as L from "leaflet"
import { getTagsDiffMode, setTagsDiffMode } from "../_local-storage"
import { qsEncode, qsParse } from "../_qs"
import { getPageTitle } from "../_title"
import { focusManyMapObjects, focusMapObject } from "../leaflet/_focus-layer"
import { getBaseFetchController } from "./_base-fetch"
import { initializeElementContent } from "./_element"
import type { IndexController } from "./_router"

const paginationDistance = 2

/** Create a new element history controller */
export const getElementHistoryController = (map: L.Map): IndexController => {
    let loadMatchGroups: { [key: string]: string } | null = null

    const base = getBaseFetchController(map, "element-history", (sidebarContent) => {
        // Get elements
        const sidebarTitleElement = sidebarContent.querySelector(".sidebar-title") as HTMLElement
        const sidebarTitle = sidebarTitleElement.textContent

        // Set page title
        document.title = getPageTitle(sidebarTitle)

        // Handle not found
        const tagsDiffCheckbox = sidebarContent.querySelector("input.tags-diff-mode")
        if (!tagsDiffCheckbox) return

        tagsDiffCheckbox.checked = getTagsDiffMode()
        tagsDiffCheckbox.addEventListener("change", () => {
            setTagsDiffMode(tagsDiffCheckbox.checked)
            controller.unload()
            controller.load(loadMatchGroups)
        })

        const versionSections = sidebarContent.querySelectorAll("div.version-section")
        for (const versionSection of versionSections) {
            const elements = initializeElementContent(map, versionSection)
            versionSection.addEventListener("mouseenter", () => focusManyMapObjects(map, elements)) // focus elements
            versionSection.addEventListener("mouseleave", () => focusMapObject(map, null)) // remove focus
        }

        const paginationContainer = sidebarContent.querySelector("ul.history-pagination")
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
                anchor.textContent = i.toString()
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
    })

    const controller: IndexController = {
        load: (matchGroups) => {
            const { type, id } = matchGroups
            const params = qsParse(location.search.substring(1))
            params.tags_diff_mode = getTagsDiffMode().toString()
            const url = `/api/partial/${type}/${id}/history?${qsEncode(params)}`
            loadMatchGroups = matchGroups
            base.load({ url })
        },
        unload: () => {
            focusMapObject(map, null)
            base.unload()
        },
    }
    return controller
}
