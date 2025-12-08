import { getBaseFetchController } from "@index/_base-fetch"
import { initializeElementContent } from "@index/element"
import { tagsDiffStorage } from "@lib/local-storage"
import { type FocusLayerPaint, focusObjects } from "@lib/map/layers/focus-layer"
import { convertRenderElementsData } from "@lib/map/render-objects"
import { memoize } from "@lib/memoize"
import type { RenderElementsData } from "@lib/proto/shared_pb"
import { configureStandardPagination } from "@lib/standard-pagination"
import { setPageTitle } from "@lib/title"
import { effect, signal } from "@preact/signals-core"
import { Tooltip } from "bootstrap"
import type { Map as MaplibreMap } from "maplibre-gl"
import type { IndexController } from "./router"

const THEME_COLOR = "#f60"
const focusPaint: FocusLayerPaint = {
    "fill-color": THEME_COLOR,
    "fill-opacity": 0.5,
    "line-color": THEME_COLOR,
    "line-opacity": 1,
    "line-width": 4,
    "circle-radius": 10,
    "circle-color": THEME_COLOR,
    "circle-opacity": 0.4,
    "circle-stroke-color": THEME_COLOR,
    "circle-stroke-opacity": 1,
    "circle-stroke-width": 3,
}

/** Create a new element history controller */
export const getElementHistoryController = (map: MaplibreMap) => {
    const base = getBaseFetchController(map, "element-history", (sidebarContent) => {
        for (const element of sidebarContent.querySelectorAll(
            "[data-bs-toggle=tooltip]",
        )) {
            new Tooltip(element)
        }

        // Get elements
        const sidebarTitleElement = sidebarContent.querySelector(".sidebar-title")!
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
        const paginationContainers = sidebarContent.querySelectorAll("ul.pagination")
        const disposePaginationEffect = effect(() => {
            for (const pagination of paginationContainers) {
                pagination.dataset.action = pagination.dataset.actionTemplate!.replace(
                    "{tags_diff}",
                    tagsDiff.toString(),
                )
            }

            let disposeElementContent: (() => void) | undefined

            const disposePagination = configureStandardPagination(sidebarContent, {
                loadCallback: (renderContainer) => {
                    const versionSections =
                        renderContainer.querySelectorAll("div.version-section")
                    for (const versionSection of versionSections) {
                        let render: RenderElementsData
                        ;[render, disposeElementContent] = initializeElementContent(
                            map,
                            versionSection,
                        )
                        const elements = memoize(() =>
                            convertRenderElementsData(render),
                        )
                        versionSection.addEventListener("mouseenter", () =>
                            focusObjects(map, elements(), focusPaint),
                        )
                        versionSection.addEventListener("mouseleave", () =>
                            focusObjects(map),
                        )
                    }
                },
            })

            return () => {
                disposePagination()
                disposeElementContent?.()
            }
        })

        return () => {
            disposePaginationEffect()
            focusObjects(map)
        }
    })

    const controller: IndexController = {
        load: ({ type, id }) => {
            base.load(`/partial/${type}/${id}/history`)
        },
        unload: base.unload,
    }
    return controller
}
