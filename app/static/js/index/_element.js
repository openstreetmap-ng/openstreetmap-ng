import i18next from "i18next"
import * as L from "leaflet"
import { getPageTitle } from "../_title.js"
import { focusMapObject } from "../leaflet/_focus-layer-util.js"
import { getBaseFetchController } from "./_base-fetch.js"

const emptyTags = new Map()

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
        const elementsSection = sidebarContent.querySelector(".elements")
        // TODO: (version X) in title

        // Set page title
        document.title = getPageTitle(sidebarTitle)

        // Handle not found
        if (!sidebarTitleElement.dataset.params) return

        // Get params
        const params = JSON.parse(sidebarTitleElement.dataset.params)
        const paramsType = params.type
        const paramsId = params.id
        const bounds = params.bounds
        const elements = params.elements

        // Not all elements have a bounding box
        if (bounds) {
            // TODO: correct params
            // focusMapObject(map, {
            //     type: paramsType,
            //     id: paramsId,
            //     version: 0, // currently unused
            //     tags: emptyTags, // currently unused
            //     bounds: bounds,
            // })

            // Focus on the element if it's offscreen
            const [minLon, minLat, maxLon, maxLat] = bounds
            const latLngBounds = L.latLngBounds(L.latLng(minLat, minLon), L.latLng(maxLat, maxLon))
            if (!map.getBounds().contains(latLngBounds)) {
                map.fitBounds(latLngBounds, { animate: false })
            }
        }

        // Not all elements have members
        if (elementsSection) {
            const isWay = paramsType === "way"
            renderElements(elementsSection, elements, isWay)
        }
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
    const tbody = elementsSection.querySelector("tbody")

    const elementsLength = elements.length
    const totalPages = Math.ceil(elementsLength / elementsPerPage)
    let currentPage = 1

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
            linkLatest.textContent = element.name ? `${element.name} (${element.id})` : element.id
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
    updateTable()
}
