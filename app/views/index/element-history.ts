import { effect, signal } from "@preact/signals-core"
import type { Map as MaplibreMap } from "maplibre-gl"
import { tagsDiffStorage } from "../lib/local-storage"
import { type FocusLayerPaint, focusObjects } from "../lib/map/layers/focus-layer"
import { convertRenderElementsData } from "../lib/map/render-objects"
import { configureStandardPagination } from "../lib/standard-pagination"
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

        tagsDiffCheckbox.checked = tagsDiffStorage.get()
        const tagsDiff = signal(tagsDiffCheckbox.checked)

        tagsDiffCheckbox.addEventListener("change", () => {
            tagsDiffStorage.set(tagsDiffCheckbox.checked)
            tagsDiff.value = tagsDiffCheckbox.checked
        })

        // Update pagination
        const disposePaginationEffect = effect(() => {
            for (const pagination of sidebarContent.querySelectorAll("ul.pagination")) {
                pagination.dataset.action = pagination.dataset.actionTemplate.replace(
                    "{tags_diff}",
                    tagsDiff.toString(),
                )
            }

            const disposePagination = configureStandardPagination(
                sidebarContent,
                () => {
                    const versionSections =
                        sidebarContent.querySelectorAll("div.version-section")
                    for (const versionSection of versionSections) {
                        const params = initializeElementContent(map, versionSection)
                        const elements = staticCache(() =>
                            convertRenderElementsData(params.render),
                        )
                        versionSection.addEventListener("mouseenter", () =>
                            focusObjects(map, elements(), focusPaint),
                        )
                        versionSection.addEventListener("mouseleave", () =>
                            focusObjects(map),
                        )
                    }
                },
            )

            return disposePagination
        })

        return disposePaginationEffect
    })

    const controller: IndexController = {
        load: ({ type, id }) => {
            base.load(`/partial/${type}/${id}/history`)
        },
        unload: () => {
            focusObjects(map)
            base.unload()
        },
    }
    return controller
}
