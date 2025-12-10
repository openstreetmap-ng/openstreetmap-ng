import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import { getBaseFetchController } from "@index/_base-fetch"
import type { IndexController } from "@index/router"
import { type ElementType, getFeatureIcon } from "@lib/feature-icons"
import { type FocusLayerPaint, focusObjects } from "@lib/map/layers/focus-layer"
import { convertRenderElementsData } from "@lib/map/render-objects"
import {
    PartialElementParams_ElementType,
    type PartialElementParams_Entry,
    PartialElementParamsSchema,
} from "@lib/proto/shared_pb"
import { configureStandardPagination } from "@lib/standard-pagination"
import { configureTagsFormat } from "@lib/tags-format"
import { setPageTitle } from "@lib/title"
import i18next from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"

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

const ELEMENTS_PER_PAGE = 20

export const getElementController = (map: MaplibreMap): IndexController => {
    const base = getBaseFetchController(map, "element", (sidebarSection) => {
        const sidebarContent = sidebarSection.querySelector("div.sidebar-content")!
        const sidebarTitleElement = sidebarContent.querySelector(".sidebar-title")!
        setPageTitle(sidebarTitleElement.textContent)

        // Handle not found
        if (!sidebarContent.dataset.params) return

        const [render, diposeElementContent] = initializeElementContent(
            map,
            sidebarContent,
        )
        const elements = convertRenderElementsData(render)
        focusObjects(map, elements, focusPaint)

        return () => {
            diposeElementContent()
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

export const initializeElementContent = (map: MaplibreMap, container: HTMLElement) => {
    console.debug("initializeElementContent")

    // Populate feature icons from data attributes
    for (const img of container.querySelectorAll("img[data-feature-icon]")) {
        const tags = JSON.parse(img.dataset.tags!)
        const type = img.dataset.type as ElementType
        const icon = getFeatureIcon(tags, type)
        if (icon) {
            img.src = `/static/img/element/${icon.filename}`
            img.title = icon.title
            img.classList.remove("d-none")
        }
    }

    // Enhance tags table
    configureTagsFormat(container.querySelector<HTMLElement>("div.tags"))

    const locationButton = container.querySelector(".location-container button")
    locationButton?.addEventListener("click", () => {
        // On location click, pan the map
        const dataset = locationButton!.dataset
        console.debug("onLocationButtonClick", dataset)
        const lon = Number.parseFloat(dataset.lon!)
        const lat = Number.parseFloat(dataset.lat!)
        map.flyTo({ center: [lon, lat], zoom: Math.max(map.getZoom(), 15) })
    })

    const params = fromBinary(
        PartialElementParamsSchema,
        base64Decode(container.dataset.params!),
    )
    const disposeList: (() => void)[] = []

    const parentsContainer = container.querySelector("div.parents")
    if (parentsContainer)
        disposeList.push(
            renderElementsComponent(parentsContainer, params.parents, false),
        )

    const membersContainer = container.querySelector("div.elements")
    if (membersContainer)
        disposeList.push(
            renderElementsComponent(
                membersContainer,
                params.members,
                params.type === PartialElementParams_ElementType.way,
            ),
        )

    return [
        params.render!,
        () => {
            for (const dispose of disposeList) dispose()
        },
    ] as const
}

const renderElementsComponent = (
    elementsSection: HTMLElement,
    elements: PartialElementParams_Entry[],
    isWay: boolean,
) => {
    console.debug("renderElementsComponent", elements.length)

    const entryTemplate = elementsSection.querySelector("template.entry")!
    const titleElement = elementsSection.querySelector(".title")!
    const paginationContainer = elementsSection.querySelector("ul.pagination")!

    // Calculate pagination
    const elementsLength = elements.length
    const totalPages = Math.ceil(elementsLength / ELEMENTS_PER_PAGE)
    paginationContainer.dataset.pages = totalPages.toString()

    if (totalPages <= 1) {
        paginationContainer.parentElement!.classList.add("d-none")
    }

    const updateTitle = (page: number) => {
        let count: string
        if (totalPages > 1) {
            const from = (page - 1) * ELEMENTS_PER_PAGE + 1
            const to = Math.min(page * ELEMENTS_PER_PAGE, elementsLength)
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
            // @ts-expect-error
            newTitle = i18next.t("browse.changeset.node", { count })
        } else if (elementsSection.classList.contains("parents")) {
            newTitle = `${i18next.t("browse.part_of")} (${count})`
        } else {
            newTitle = `${i18next.t("browse.relation.members")} (${count})`
        }
        titleElement.textContent = newTitle
    }

    const updateTable = (page: number, renderContainer: HTMLElement) => {
        const renderFragment = document.createDocumentFragment()

        const iStart = (page - 1) * ELEMENTS_PER_PAGE
        const iEnd = Math.min(page * ELEMENTS_PER_PAGE, elementsLength)
        for (let i = iStart; i < iEnd; i++) {
            const element = elements[i]
            const type = element.type

            const entryFragment = entryTemplate.content.cloneNode(
                true,
            ) as DocumentFragment
            const iconImg = entryFragment.querySelector("img")!
            const content = entryFragment.querySelector("td:last-child")!

            const elementType = PartialElementParams_ElementType[type] as ElementType
            const icon = getFeatureIcon(element.tags, elementType)
            if (icon) {
                iconImg.src = `/static/img/element/${icon.filename}`
                iconImg.title = icon.title
            } else {
                iconImg.remove()
            }

            // Prefer static translation strings to ease automation
            let typeStr: string
            if (type === PartialElementParams_ElementType.node) {
                typeStr = i18next.t("javascripts.query.node")
            } else if (type === PartialElementParams_ElementType.way) {
                typeStr = i18next.t("javascripts.query.way")
            } else {
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
            linkLatest.href = `/${PartialElementParams_ElementType[type]}/${element.id}`

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

            renderFragment.appendChild(entryFragment)
        }

        renderContainer.innerHTML = ""
        renderContainer.appendChild(renderFragment)
    }

    const disposePagination = configureStandardPagination(elementsSection, {
        initialPage: 1,
        customLoader: (renderContainer: HTMLElement, page: number) => {
            updateTitle(page)
            updateTable(page, renderContainer)
        },
    })

    return disposePagination
}
