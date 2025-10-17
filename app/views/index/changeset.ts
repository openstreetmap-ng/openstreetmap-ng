import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import i18next from "i18next"

import type { MapLibreEvent, Map as MaplibreMap } from "maplibre-gl"
import { renderColorPreviews } from "../lib/color-preview"
import { type FocusLayerPaint, focusObjects } from "../lib/map/layers/focus-layer.ts"
import { makeBoundsMinimumSize } from "../lib/map/utils"
import {
    type PartialChangesetParams,
    type PartialChangesetParams_Element,
    PartialChangesetParamsSchema,
} from "../lib/proto/shared_pb"
import { configureReportButtonsLazy } from "../lib/report-modal"
import { configureStandardForm } from "../lib/standard-form"
import { configureStandardPagination } from "../lib/standard-pagination"
import { setPageTitle } from "../lib/title"
import type { Bounds, OSMChangeset } from "../lib/types"
import { getBaseFetchController } from "./_base-fetch.ts"
import type { IndexController } from "./_router"

const focusPaint: FocusLayerPaint = Object.freeze({
    "fill-opacity": 0,
    "line-color": "#f90",
    "line-opacity": 1,
    "line-width": 3,
})

const elementsPerPage = 20

/** Create a new changeset controller */
export const getChangesetController = (map: MaplibreMap): IndexController => {
    let params: PartialChangesetParams | null = null
    let paramsBounds: Bounds[] | null = null

    const base = getBaseFetchController(map, "changeset", (sidebarContent) => {
        renderColorPreviews(sidebarContent)
        configureReportButtonsLazy(sidebarContent)

        const sidebarTitleElement = sidebarContent.querySelector(
            ".sidebar-title",
        ) as HTMLElement
        const elementsSection = sidebarContent.querySelector("div.elements")
        setPageTitle(sidebarTitleElement.textContent)

        // Handle not found
        if (!sidebarTitleElement.dataset.params) return

        // Get params
        params = fromBinary(
            PartialChangesetParamsSchema,
            base64Decode(sidebarTitleElement.dataset.params),
        )

        // Optionally update on map zoom (not all changesets have bounds)
        if (params.bounds.length) {
            paramsBounds = []
            for (const bounds of params.bounds) {
                const { minLon, minLat, maxLon, maxLat } = bounds
                paramsBounds.push([minLon, minLat, maxLon, maxLat])
            }
            // Listen for events and run initial update
            map.on("zoomend", refocus)
            refocus()
        }

        const disposeElements = renderElements(elementsSection, {
            node: params.nodes,
            way: params.ways,
            relation: params.relations,
        })

        const disposePagination = configureStandardPagination(
            sidebarContent.querySelector("div.changeset-comments-pagination"),
        )

        // On success callback, reload the changeset
        configureStandardForm(
            sidebarContent.querySelector("form.subscription-form"),
            reload,
        )
        configureStandardForm(sidebarContent.querySelector("form.comment-form"), reload)

        return () => {
            disposeElements()
            disposePagination()
            map.off("zoomend", refocus)
            focusObjects(map)
        }
    })

    const refocus = (e?: MapLibreEvent): void => {
        // On map zoom change, refocus the changeset (due to size change)
        const object: OSMChangeset = {
            type: "changeset",
            id: params.id,
            bounds: paramsBounds.map((b) => makeBoundsMinimumSize(map, b)),
        }
        focusObjects(map, [object], focusPaint, null, {
            // Fit the bounds only on the initial update
            fitBounds: !e,
        })
    }

    const controller: IndexController = {
        load: ({ id }) => {
            base.load(`/partial/changeset/${id}`)
        },
        unload: base.unload,
    }
    const reload = () => {
        controller.unload()
        controller.load({ id: params.id.toString() })
    }
    return controller
}

/** Render elements component */
const renderElements = (
    elementsSection: HTMLElement,
    elements: { [key: string]: PartialChangesetParams_Element[] },
): (() => void) => {
    console.debug("renderElements")

    const groupTemplate = elementsSection.querySelector("template.group")
    const entryTemplate = elementsSection.querySelector("template.entry")
    const fragment = document.createDocumentFragment()
    const disposeList: (() => void)[] = []

    for (const [type, elementsType] of Object.entries(elements)) {
        if (!elementsType.length) continue
        const [renderFragment, disposePagination] = renderElementType(
            groupTemplate,
            entryTemplate,
            type,
            elementsType,
        )
        fragment.appendChild(renderFragment)
        disposeList.push(disposePagination)
    }

    if (fragment.children.length) {
        elementsSection.innerHTML = ""
        elementsSection.appendChild(fragment)
    } else {
        elementsSection.remove()
    }

    return () => {
        for (const dispose of disposeList) dispose()
    }
}

/** Render elements of a specific type */
const renderElementType = (
    groupTemplate: HTMLTemplateElement,
    entryTemplate: HTMLTemplateElement,
    type: string,
    elements: PartialChangesetParams_Element[],
): [DocumentFragment, () => void] => {
    console.debug("renderElementType", type, elements)

    const groupFragment = groupTemplate.content.cloneNode(true) as DocumentFragment
    const titleElement = groupFragment.querySelector(".title")
    const paginationContainer = groupFragment.querySelector("ul.pagination")

    // Calculate pagination
    const elementsLength = elements.length
    const totalPages = Math.ceil(elementsLength / elementsPerPage)
    paginationContainer.dataset.pages = totalPages.toString()

    if (totalPages <= 1) {
        paginationContainer.parentElement.classList.add("d-none")
    }

    const updateTitle = (page: number): void => {
        let count: string
        if (totalPages > 1) {
            const from = (page - 1) * elementsPerPage + 1
            const to = Math.min(page * elementsPerPage, elementsLength)
            count = i18next.t("pagination.range", {
                x: `${from}-${to}`,
                y: elementsLength,
            })
        } else {
            count = elementsLength.toString()
        }

        // Prefer static translation strings to ease automation
        let newTitle: string
        if (type === "node") {
            // @ts-expect-error
            newTitle = i18next.t("browse.changeset.node", { count })
        } else if (type === "way") {
            // @ts-expect-error
            newTitle = i18next.t("browse.changeset.way", { count })
        } else if (type === "relation") {
            // @ts-expect-error
            newTitle = i18next.t("browse.changeset.relation", { count })
        }
        titleElement.textContent = newTitle
    }

    const updateTable = (page: number, renderContainer: HTMLElement): void => {
        const renderFragment = document.createDocumentFragment()

        const iStart = (page - 1) * elementsPerPage
        const iEnd = Math.min(page * elementsPerPage, elementsLength)
        for (let i = iStart; i < iEnd; i++) {
            const element = elements[i]

            const entryFragment = entryTemplate.content.cloneNode(
                true,
            ) as DocumentFragment
            const iconImg = entryFragment.querySelector("img")
            const linkLatest = entryFragment.querySelector("a.link-latest")
            const linkVersion = entryFragment.querySelector("a.link-version")

            if (element.icon) {
                iconImg.src = `/static/img/element/${element.icon.icon}`
                iconImg.title = element.icon.title
            } else {
                iconImg.remove()
            }

            if (!element.visible) {
                linkLatest.parentElement.parentElement.classList.add("deleted")
            }

            if (element.name) {
                const bdi = document.createElement("bdi")
                bdi.textContent = element.name
                linkLatest.appendChild(bdi)
                const span = document.createElement("span")
                span.textContent = ` (${element.id})`
                linkLatest.appendChild(span)
            } else {
                linkLatest.textContent = element.id.toString()
            }
            linkLatest.href = `/${type}/${element.id}`
            linkVersion.textContent = `v${element.version}`
            linkVersion.href = `/${type}/${element.id}/history/${element.version}`
            renderFragment.appendChild(entryFragment)
        }

        renderContainer.innerHTML = ""
        renderContainer.appendChild(renderFragment)
    }

    const disposePagination = configureStandardPagination(groupFragment, {
        initialPage: 1,
        customLoader: (page: number, renderContainer: HTMLElement) => {
            updateTitle(page)
            updateTable(page, renderContainer)
        },
    })

    return [groupFragment, disposePagination]
}
