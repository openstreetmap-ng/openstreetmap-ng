import i18next from "i18next"
import * as L from "leaflet"
import { renderColorPreviews } from "../_color-preview.js"
import { configureStandardForm } from "../_standard-form.js"
import { getPageTitle } from "../_title.js"
import { focusMapObject } from "../leaflet/_focus-layer-util.js"
import { getBaseFetchController } from "./_base-fetch.js"

const emptyTags = new Map()

const elementsPerPage = 20
const paginationDistance = 2

/**
 * Create a new changeset controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getChangesetController = (map) => {
    const onLoaded = (sidebarContent) => {
        renderColorPreviews()

        // Get elements
        const sidebarTitleElement = sidebarContent.querySelector(".sidebar-title")
        const sidebarTitle = sidebarTitleElement.textContent
        const subscriptionForm = sidebarContent.querySelector("form.subscription-form")
        const commentForm = sidebarContent.querySelector("form.comment-form")
        const elementsSection = sidebarContent.querySelector(".elements")

        // Set page title
        document.title = getPageTitle(sidebarTitle)

        // Get params
        const params = JSON.parse(sidebarTitleElement.dataset.params)
        const paramsId = params.id
        const bounds = params.bounds
        const elements = params.elements

        // Not all changesets have a bounding box
        if (bounds) {
            focusMapObject(map, {
                type: "changeset",
                id: paramsId,
                tags: emptyTags, // currently unused
                bounds: bounds,
            })

            // Focus on the changeset if it's offscreen
            const [minLon, minLat, maxLon, maxLat] = bounds
            const latLngBounds = L.latLngBounds(L.latLng(minLat, minLon), L.latLng(maxLat, maxLon))
            if (!map.getBounds().contains(latLngBounds)) {
                map.fitBounds(latLngBounds, { animate: false })
            }
        }

        renderElements(elementsSection, elements)

        // On success callback, reload the changeset
        const onFormSuccess = () => {
            console.debug("onFormSuccess", paramsId)
            base.unload()
            base.load({ id: paramsId })
        }

        // Listen for events
        if (subscriptionForm) configureStandardForm(subscriptionForm, onFormSuccess)
        if (commentForm) configureStandardForm(commentForm, onFormSuccess)
    }

    const base = getBaseFetchController(map, "changeset", onLoaded)
    const baseLoad = base.load
    const baseUnload = base.unload

    base.load = ({ id }) => {
        const url = `/api/web/partial/changeset/${id}`
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
 * @returns {void}
 */
const renderElements = (elementsSection, elements) => {
    console.debug("renderElements")

    const groupTemplate = elementsSection.querySelector("template.group")
    const entryTemplate = elementsSection.querySelector("template.entry")

    const fragment = document.createDocumentFragment()

    for (const type of ['way', 'relation', 'node']) {
        const elementsType = elements[type]
        if (elementsType.length) {
            fragment.appendChild(renderElementType(groupTemplate, entryTemplate, type, elementsType))
        }
    }

    if (fragment.children.length) {
        elementsSection.innerHTML = ""
        elementsSection.appendChild(fragment)
    } else {
        elementsSection.remove()
    }
}

/**
 * Render elements of a specific type
 * @param {HTMLTemplateElement} groupTemplate Group template
 * @param {HTMLTemplateElement} entryTemplate Entry template
 * @param {string} type Element type
 * @param {object[]} elements Elements data
 * @returns {DocumentFragment} Fragment
 */
const renderElementType = (groupTemplate, entryTemplate, type, elements) => {
    console.debug("renderElementType", type, elements)

    const groupFragment = groupTemplate.content.cloneNode(true)
    const titleElement = groupFragment.querySelector(".title")
    const tbody = groupFragment.querySelector("tbody")

    const elementsLength = elements.length
    const totalPages = Math.ceil(elementsLength / elementsPerPage)
    let currentPage = 1

    const updateTitle = () => {
        const data = totalPages > 1 ? {
            count: elementsLength,
            x: (currentPage - 1) * elementsPerPage + 1,
            y: Math.min(currentPage * elementsPerPage, elementsLength),
        } : {
            count: elementsLength,
        }

        // prefer static translation strings to ease automation
        let newTitle
        if (type === 'node') {
            newTitle = totalPages > 1
                ? i18next.t('browse.changeset.node_paginated', data)
                : i18next.t('browse.changeset.node', data)
        } else if (type === 'way') {
            newTitle = totalPages > 1
                ? i18next.t('browse.changeset.way_paginated', data)
                : i18next.t('browse.changeset.way', data)
        } else if (type === 'relation') {
            newTitle = totalPages > 1
                ? i18next.t('browse.changeset.relation_paginated', data)
                : i18next.t('browse.changeset.relation', data)
        }
        titleElement.textContent = newTitle
    }

    const updateTable = () => {
        const tbodyFragment = document.createDocumentFragment()

        const iStart = (currentPage - 1) * elementsPerPage
        const iEnd = Math.min(currentPage * elementsPerPage, elementsLength)
        for (let i = iStart; i < iEnd; i++) {
            const entryFragment = entryTemplate.content.cloneNode(true)

            const iconImg = entryFragment.querySelector("img")
            const linkLatest = entryFragment.querySelector("a.link-latest")
            const linkVersion = entryFragment.querySelector("a.link-version")

            const element = elements[i]

            if (element.icon) {
                iconImg.src = `/static/img/element/${element.icon}`
                iconImg.title = element.icon_title
            } else {
                iconImg.remove()
            }

            if (!element.visible) {
                linkLatest.parentElement.classList.add("deleted")
            }

            linkLatest.textContent = element.name ? `${element.name} (${element.id})` : element.id
            linkLatest.href = `/${type}/${element.id}`

            linkVersion.textContent = `v${element.version}`
            linkVersion.href = `/${type}/${element.id}/history/${element.version}`

            tbodyFragment.appendChild(entryFragment)
        }

        tbody.innerHTML = ""
        tbody.appendChild(tbodyFragment)
    }

    if (totalPages > 1) {
        const paginationContainer = groupFragment.querySelector(".pagination")

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
        groupFragment.querySelector("nav").remove()
    }

    // Initial update
    updateTitle()
    updateTable()

    return groupFragment
}
