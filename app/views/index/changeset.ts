import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import i18next from "i18next"

import type { MapLibreEvent, Map as MaplibreMap } from "maplibre-gl"
import { renderColorPreviews } from "../lib/color-preview"
import { configureStandardForm } from "../lib/standard-form"
import { configureStandardPagination } from "../lib/standard-pagination"
import { setPageTitle } from "../lib/title"
import type { Bounds, OSMChangeset } from "../lib/types"
import { type FocusLayerPaint, focusObjects } from "../lib/map/focus-layer"
import { makeBoundsMinimumSize } from "../lib/map/utils"
import {
    type PartialChangesetParams,
    PartialChangesetParamsSchema,
    type PartialChangesetParams_Element,
} from "../lib/proto/shared_pb"
import { getBaseFetchController } from "./_base-fetch.ts"
import type { IndexController } from "./_router"

const focusPaint: FocusLayerPaint = Object.freeze({
    "fill-opacity": 0,
    "line-color": "#f90",
    "line-opacity": 1,
    "line-width": 3,
})

const elementsPerPage = 20
const paginationDistance = 2

/** Create a new changeset controller */
export const getChangesetController = (map: MaplibreMap): IndexController => {
    let params: PartialChangesetParams | null = null
    let paramsBounds: Bounds[] | null = null

    const base = getBaseFetchController(map, "changeset", (sidebarContent) => {
        renderColorPreviews(sidebarContent)

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

        renderElements(elementsSection, {
            node: params.nodes,
            way: params.ways,
            relation: params.relations,
        })

        configureStandardPagination(
            sidebarContent.querySelector("div.changeset-comments-pagination"),
        )

        // On success callback, reload the changeset
        configureStandardForm(
            sidebarContent.querySelector("form.subscription-form"),
            reload,
        )
        configureStandardForm(sidebarContent.querySelector("form.comment-form"), reload)
    })

    const refocus = (e?: MapLibreEvent): void => {
        // On map zoom change, refocus the changeset (due to size change)
        const object: OSMChangeset = {
            type: "changeset",
            id: params.id,
            bounds: paramsBounds.map((b) => makeBoundsMinimumSize(map, b)),
        }
        focusObjects(map, [object], focusPaint, {
            // Fit the bounds only on the initial update
            fitBounds: !e,
        })
    }

    const controller: IndexController = {
        load: ({ id }) => {
            base.load(`/partial/changeset/${id}`)
        },
        unload: () => {
            map.off("zoomend", refocus)
            focusObjects(map)
            base.unload()
        },
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
): void => {
    console.debug("renderElements")

    const groupTemplate = elementsSection.querySelector("template.group")
    const entryTemplate = elementsSection.querySelector("template.entry")
    const fragment = document.createDocumentFragment()

    for (const [type, elementsType] of Object.entries(elements)) {
        if (!elementsType.length) continue
        fragment.appendChild(
            renderElementType(groupTemplate, entryTemplate, type, elementsType),
        )
    }

    if (fragment.children.length) {
        elementsSection.innerHTML = ""
        elementsSection.appendChild(fragment)
    } else {
        elementsSection.remove()
    }
}

/** Render elements of a specific type */
const renderElementType = (
    groupTemplate: HTMLTemplateElement,
    entryTemplate: HTMLTemplateElement,
    type: string,
    elements: PartialChangesetParams_Element[],
): DocumentFragment => {
    console.debug("renderElementType", type, elements)

    const groupFragment = groupTemplate.content.cloneNode(true) as DocumentFragment
    const titleElement = groupFragment.querySelector(".title")
    const tbody = groupFragment.querySelector("tbody")

    // Calculate pagination
    const elementsLength = elements.length
    const totalPages = Math.ceil(elementsLength / elementsPerPage)
    let currentPage = 1

    const updateTitle = (): void => {
        let count: string
        if (totalPages > 1) {
            const from = (currentPage - 1) * elementsPerPage + 1
            const to = Math.min(currentPage * elementsPerPage, elementsLength)
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
            // @ts-ignore
            newTitle = i18next.t("browse.changeset.node", { count })
        } else if (type === "way") {
            // @ts-ignore
            newTitle = i18next.t("browse.changeset.way", { count })
        } else if (type === "relation") {
            // @ts-ignore
            newTitle = i18next.t("browse.changeset.relation", { count })
        }
        titleElement.textContent = newTitle
    }

    const updateTable = (): void => {
        const tbodyFragment = document.createDocumentFragment()

        const iStart = (currentPage - 1) * elementsPerPage
        const iEnd = Math.min(currentPage * elementsPerPage, elementsLength)
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
            tbodyFragment.appendChild(entryFragment)
        }

        tbody.innerHTML = ""
        tbody.appendChild(tbodyFragment)
    }

    // Optionally configure pagination controls
    if (totalPages > 1) {
        const paginationContainer = groupFragment.querySelector(".pagination")

        const updatePagination = (): void => {
            console.debug("updatePagination", currentPage)

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

                const button = document.createElement("button")
                button.type = "button"
                button.classList.add("page-link")
                button.textContent = i.toString()
                li.appendChild(button)

                if (i === currentPage) {
                    li.classList.add("active")
                    li.ariaCurrent = "page"
                } else {
                    button.addEventListener("click", () => {
                        currentPage = i
                        updateTitle()
                        updateTable()
                        updatePagination()
                    })
                }

                paginationFragment.appendChild(li)
            }

            paginationContainer.innerHTML = ""
            paginationContainer.appendChild(paginationFragment)
        }

        updatePagination()
    } else {
        groupFragment.querySelector("nav").remove()
    }

    // Initial update
    updateTitle()
    updateTable()
    return groupFragment
}
