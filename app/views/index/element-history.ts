import type { Map as MaplibreMap } from "maplibre-gl"
import { tagsDiffStorage } from "../lib/local-storage"
import { type FocusLayerPaint, focusObjects } from "../lib/map/layers/focus-layer"
import { convertRenderElementsData } from "../lib/map/render-objects"
import { qsEncode, qsParse } from "../lib/qs"
import { setPageTitle } from "../lib/title"
import { staticCache } from "../lib/utils"
import { getBaseFetchController } from "./_base-fetch"
import type { IndexController } from "./_router"
import { initializeElementContent } from "./element"

const themeColor = "#f60"
const focusPaint: FocusLayerPaint = Object.freeze({
    "fill-color": themeColor,
    "fill-opacity": 0.5,
    "line-color": themeColor,
    "line-opacity": 1,
    "line-width": 4,
    "circle-radius": 10,
    "circle-color": themeColor,
    "circle-opacity": 0.4,
    "circle-stroke-color": themeColor,
    "circle-stroke-opacity": 1,
    "circle-stroke-width": 3,
})

const paginationDistance = 2

/** Create a new element history controller */
export const getElementHistoryController = (map: MaplibreMap): IndexController => {
    const base = getBaseFetchController(map, "element-history", (sidebarContent) => {
        // Get elements
        const sidebarTitleElement = sidebarContent.querySelector(
            ".sidebar-title",
        ) as HTMLElement
        setPageTitle(sidebarTitleElement.textContent)

        // Handle not found
        const tagsDiffCheckbox = sidebarContent.querySelector("input.tags-diff")
        if (!tagsDiffCheckbox) return

        tagsDiffCheckbox.addEventListener("change", () => {
            tagsDiffStorage.set(tagsDiffCheckbox.checked)
            controller.unload()
            controller.load(loadMatchGroups)
        })

        const versionSections = sidebarContent.querySelectorAll("div.version-section")
        for (const versionSection of versionSections) {
            const params = initializeElementContent(map, versionSection)
            const elements = staticCache(() => convertRenderElementsData(params.render))
            versionSection.addEventListener("mouseenter", () =>
                focusObjects(map, elements(), focusPaint),
            ) // focus elements
            versionSection.addEventListener("mouseleave", () => focusObjects(map)) // remove focus
        }

        const paginationContainer = sidebarContent.querySelector(
            "ul.history-pagination",
        )
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

    let loadMatchGroups: { [key: string]: string } | null = null
    const controller: IndexController = {
        load: (matchGroups) => {
            const { type, id } = matchGroups
            loadMatchGroups = matchGroups
            const params = qsParse(window.location.search)
            params.tags_diff = tagsDiffStorage.get().toString()
            const url = `/partial/${type}/${id}/history?${qsEncode(params)}`
            base.load(url)
        },
        unload: () => {
            focusObjects(map)
            base.unload()
        },
    }
    return controller
}
