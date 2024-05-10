import i18next from "i18next"
import * as L from "leaflet"
import { parseElements } from "../_format07.js"
import { getPageTitle } from "../_title.js"
import { focusManyMapObjects, focusMapObject } from "../leaflet/_focus-layer-util.js"
import { getBaseFetchController } from "./_base-fetch.js"

const elementsPerPage = 20
const paginationDistance = 2

/**
 * Create a new element controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getElementController = (map) => {
    const onLoaded = (sidebarContent) => {
        // Get elements
        const sidebarTitleElement = sidebarContent.querySelector(".sidebar-title")
        const sidebarTitle = sidebarTitleElement.textContent
        const partOfSection = sidebarContent.querySelector(".part-of")
        const elementsSection = sidebarContent.querySelector(".elements")
        // TODO: (version X) in title

        // Set page title
        document.title = getPageTitle(sidebarTitle)

        // Handle not found
        if (!sidebarTitleElement.dataset.params) return

        // Get params
        const params = JSON.parse(sidebarTitleElement.dataset.params)
        const paramsType = params.type
        // const paramsId = params.id

        if (partOfSection) {
            const listPartOf = params.lists.partOf
            renderElements(partOfSection, listPartOf, false)
        }

        if (elementsSection) {
            const listElements = params.lists.elements
            const isWay = paramsType === "way"
            renderElements(elementsSection, listElements, isWay)
        }

        const fullData = params.fullData
        const elementMap = parseElements(fullData)
        const elements = [
            ...elementMap.relation.values(),
            ...elementMap.way.values(),
            ...elementMap.node.values(),
        ]

        focusManyMapObjects(map, elements)
    }

    const base = getBaseFetchController(map, "element", onLoaded)
    const baseLoad = base.load
    const baseUnload = base.unload

    base.load = ({ type, id, version }) => {
        const url = `/api/web/partial/element/${type}/${id}${version ? `/version/${version}` : ""}`
        baseLoad({ url })
    }

    base.unload = () => {
        focusMapObject(map, null)
        baseUnload()
    }

    return base
}

/**
 * Render elements component
 * @param {HTMLElement} elementsSection Elements section
 * @param {object} elements Elements data
 * @param {boolean} isWay Whether the current element is a way
 * @returns {void}
 */
const renderElements = (elementsSection, elements, isWay) => {
    console.debug("renderElements", elements.length)

    const entryTemplate = elementsSection.querySelector("template.entry")
    const titleElement = elementsSection.querySelector(".title")
    const tbody = elementsSection.querySelector("tbody")

    const elementsLength = elements.length
    const totalPages = Math.ceil(elementsLength / elementsPerPage)
    let currentPage = 1

    const updateTitle = () => {
        const count = totalPages > 1 ? i18next.t('pagination.range', {
            x: `${(currentPage - 1) * elementsPerPage + 1}-${Math.min(currentPage * elementsPerPage, elementsLength)}`,
            y: elementsLength,
        }) : elementsLength

        // prefer static translation strings to ease automation
        let newTitle
        if (isWay) {
            newTitle = i18next.t('browse.changeset.node', { count })
        } else {
            newTitle = i18next.t('browse.relation.members') + ` (${count})`
        }
        titleElement.textContent = newTitle
    }

    const updateTable = () => {
        const tbodyFragment = document.createDocumentFragment()

        const iStart = (currentPage - 1) * elementsPerPage
        const iEnd = Math.min(currentPage * elementsPerPage, elementsLength)
        for (let i = iStart; i < iEnd; i++) {
            const element = elements[i]
            const type = element.type

            const entryFragment = entryTemplate.content.cloneNode(true)
            const iconImg = entryFragment.querySelector("img")
            const content = entryFragment.querySelector("td:last-child")

            if (element.icon) {
                iconImg.src = `/static/img/element/${element.icon}`
                iconImg.title = element.icon_title
            } else {
                iconImg.remove()
            }

            // prefer static translation strings to ease automation
            let typeStr
            if (type === 'node') {
                typeStr = i18next.t('javascripts.query.node')
            } else if (type === 'way') {
                typeStr = i18next.t('javascripts.query.way')
            } else if (type === 'relation') {
                typeStr = i18next.t('javascripts.query.relation')
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
                linkLatest.textContent = element.id
            }
            linkLatest.href = `/${type}/${element.id}`

            if (isWay) {
                content.appendChild(linkLatest)
            } else if (element.role) {
                content.innerHTML = i18next.t('browse.relation_member.entry_role_html', {
                    type: typeStr,
                    name: linkLatest.outerHTML,
                    role: element.role,
                    interpolation: { escapeValue: false },
                })
            } else {
                content.innerHTML = i18next.t('browse.relation_member.entry_html', {
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

        const updatePagination = () => {
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
                button.textContent = i
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
