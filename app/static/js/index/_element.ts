import i18next from "i18next"
import * as L from "leaflet"
import { getPageTitle } from "../_title"
import type { OSMNode, OSMWay } from "../_types"
import { focusManyMapObjects, focusMapObject } from "../leaflet/_focus-layer"
import { getBaseFetchController } from "./_base-fetch"
import type { IndexController } from "./_router"

// app/format/element_list.py
interface MemberListEntry {
    type: string
    id: number
    name?: string
    icon?: string
    // biome-ignore lint/style/useNamingConvention: <explanation>
    icon_title?: string
    role?: string
}

const elementsPerPage = 20
const paginationDistance = 2

/** Create a new element controller */
export const getElementController = (map: L.Map): IndexController => {
    const base = getBaseFetchController(map, "element", (sidebarSection) => {
        // Get elements
        const sidebarContent = sidebarSection.querySelector("div.sidebar-content")
        const sidebarTitleElement = sidebarContent.querySelector(".sidebar-title")
        const sidebarTitle = sidebarTitleElement.textContent

        // Set page title
        document.title = getPageTitle(sidebarTitle)

        // Handle not found
        if (!sidebarContent.dataset.params) return

        const elements = initializeElementContent(map, sidebarContent)
        focusManyMapObjects(map, elements)
    })

    return {
        load: ({ type, id, version }) => {
            const url = version ? `/api/partial/${type}/${id}/history/${version}` : `/api/partial/${type}/${id}`
            base.load({ url })
        },
        unload: () => {
            focusMapObject(map, null)
            base.unload()
        },
    }
}

/** Initialize element content */
export const initializeElementContent = (map: L.Map, container: HTMLElement): (OSMNode | OSMWay)[] => {
    console.debug("initializeElementContent")
    const partOfContainer = container.querySelector("div.part-of")
    const elementsContainer = container.querySelector("div.elements")

    // Get params
    const params = JSON.parse(container.dataset.params)
    const paramsType: string = params.type

    const locationButton = container.querySelector("button.location-btn")
    if (locationButton) {
        // On location click, pan the map
        locationButton.addEventListener("click", () => {
            const dataset = locationButton.dataset
            console.debug("onLocationButtonClick", dataset)
            const lon = Number.parseFloat(dataset.lon)
            const lat = Number.parseFloat(dataset.lat)
            const latLng = L.latLng(lat, lon)
            const currentZoom = map.getZoom()
            if (currentZoom < 16) {
                map.setView(latLng, 18)
            } else {
                map.panTo(latLng)
            }
        })
    }

    if (partOfContainer) {
        const listPartOf: MemberListEntry[] = params.lists.part_of
        renderElements(partOfContainer, listPartOf, false)
    }

    if (elementsContainer) {
        const listElements: MemberListEntry[] = params.lists.elements
        const isWay = paramsType === "way"
        renderElements(elementsContainer, listElements, isWay)
    }

    return JSON.parse(container.dataset.leaflet)
}

/** Render elements component */
const renderElements = (elementsSection: HTMLElement, elements: MemberListEntry[], isWay: boolean): void => {
    console.debug("renderElements", elements.length)

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
            count = i18next.t("pagination.range", { x: `${from}-${to}`, y: elementsLength })
        } else {
            count = elementsLength.toString()
        }

        // Prefer static translation strings to ease automation
        let newTitle: string
        if (isWay) {
            // @ts-ignore
            newTitle = i18next.t("browse.changeset.node", { count })
        } else if (elementsSection.classList.contains("part-of")) {
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

            const entryFragment = entryTemplate.content.cloneNode(true) as DocumentFragment
            const iconImg = entryFragment.querySelector("img")
            const content = entryFragment.querySelector("td:last-child")

            if (element.icon) {
                iconImg.src = `/static/img/element/${element.icon}`
                iconImg.title = element.icon_title
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
                content.innerHTML = i18next.t("browse.relation_member.entry_role_html", {
                    type: typeStr,
                    name: linkLatest.outerHTML,
                    role: element.role,
                    interpolation: { escapeValue: false },
                })
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
