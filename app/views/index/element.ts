import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import i18next from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"
import { type FocusLayerPaint, focusObjects } from "../lib/map/layers/focus-layer"
import { convertRenderElementsData } from "../lib/map/render-objects"
import {
    type PartialElementParams,
    type PartialElementParams_Entry,
    PartialElementParamsSchema,
} from "../lib/proto/shared_pb"
import { setPageTitle } from "../lib/title"
import { getBaseFetchController } from "./_base-fetch"
import type { IndexController } from "./_router"

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

const elementsPerPage = 20
const paginationDistance = 2

/** Create a new element controller */
export const getElementController = (map: MaplibreMap): IndexController => {
    const base = getBaseFetchController(map, "element", (sidebarSection) => {
        const sidebarContent = sidebarSection.querySelector("div.sidebar-content")
        const sidebarTitleElement = sidebarContent.querySelector(".sidebar-title")
        setPageTitle(sidebarTitleElement.textContent)

        // Handle not found
        if (!sidebarContent.dataset.params) return

        const params = initializeElementContent(map, sidebarContent)
        const elements = convertRenderElementsData(params.render)
        focusObjects(map, elements, focusPaint)

        return () => {
            focusObjects(map)
        }
    })

    return {
        load: ({ type, id, version }) => {
            base.load(
                version
                    ? `/partial/${type}/${id}/history/${version}`
                    : `/partial/${type}/${id}`,
            )
        },
        unload: base.unload,
    }
}

/** Initialize element content */
export const initializeElementContent = (
    map: MaplibreMap,
    container: HTMLElement,
): PartialElementParams => {
    console.debug("initializeElementContent")

    const locationButton = container.querySelector(".location-container button")
    locationButton?.addEventListener("click", () => {
        // On location click, pan the map
        const dataset = locationButton.dataset
        console.debug("onLocationButtonClick", dataset)
        const lon = Number.parseFloat(dataset.lon)
        const lat = Number.parseFloat(dataset.lat)
        map.flyTo({ center: [lon, lat], zoom: Math.max(map.getZoom(), 15) })
    })

    const params = fromBinary(
        PartialElementParamsSchema,
        base64Decode(container.dataset.params),
    )
    const parentsContainer = container.querySelector("div.parents")
    if (parentsContainer) {
        renderElementsComponent(parentsContainer, params.parents, false)
    }
    const membersContainer = container.querySelector("div.elements")
    if (membersContainer) {
        const isWay = params.type === "way"
        renderElementsComponent(membersContainer, params.members, isWay)
    }

    return params
}

/** Render elements component */
const renderElementsComponent = (
    elementsSection: HTMLElement,
    elements: PartialElementParams_Entry[],
    isWay: boolean,
): void => {
    console.debug("renderElementsComponent", elements.length)

    const entryTemplate = elementsSection.querySelector("template.entry")
    const titleElement = elementsSection.querySelector(".title")
    const tbody = elementsSection.querySelector("tbody")

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
        if (isWay) {
            // @ts-ignore
            newTitle = i18next.t("browse.changeset.node", { count })
        } else if (elementsSection.classList.contains("parents")) {
            newTitle = `${i18next.t("browse.part_of")} (${count})`
        } else {
            newTitle = `${i18next.t("browse.relation.members")} (${count})`
        }
        titleElement.textContent = newTitle
    }

    const updateTable = (): void => {
        const tbodyFragment = document.createDocumentFragment()

        const iStart = (currentPage - 1) * elementsPerPage
        const iEnd = Math.min(currentPage * elementsPerPage, elementsLength)
        for (let i = iStart; i < iEnd; i++) {
            const element = elements[i]
            const type = element.type

            const entryFragment = entryTemplate.content.cloneNode(
                true,
            ) as DocumentFragment
            const iconImg = entryFragment.querySelector("img")
            const content = entryFragment.querySelector("td:last-child")

            if (element.icon) {
                iconImg.src = `/static/img/element/${element.icon.icon}`
                iconImg.title = element.icon.title
            } else {
                iconImg.remove()
            }

            // Prefer static translation strings to ease automation
            let typeStr: string
            if (type === "node") {
                typeStr = i18next.t("javascripts.query.node")
            } else if (type === "way") {
                typeStr = i18next.t("javascripts.query.way")
            } else if (type === "relation") {
                typeStr = i18next.t("javascripts.query.relation")
            }

            const linkLatest = document.createElement("a")
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

            if (isWay) {
                content.appendChild(linkLatest)
            } else if (element.role) {
                content.innerHTML = i18next.t(
                    "browse.relation_member.entry_role_html",
                    {
                        type: typeStr,
                        name: linkLatest.outerHTML,
                        role: element.role,
                        interpolation: { escapeValue: false },
                    },
                )
            } else {
                content.innerHTML = i18next.t("browse.relation_member.entry_html", {
                    type: typeStr,
                    name: linkLatest.outerHTML,
                    interpolation: { escapeValue: false },
                })
            }

            tbodyFragment.appendChild(entryFragment)
        }

        tbody.innerHTML = ""
        tbody.appendChild(tbodyFragment)
    }

    if (totalPages > 1) {
        const paginationContainer = elementsSection.querySelector(".pagination")

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
        elementsSection.querySelector("nav").remove()
    }

    // Initial update
    updateTitle()
    updateTable()
}
