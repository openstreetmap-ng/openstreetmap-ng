import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import { getBaseFetchController } from "@index/_base-fetch"
import type { IndexController } from "@index/router"
import { type FocusLayerPaint, focusObjects } from "@lib/map/layers/focus-layer"
import { convertRenderElementsData } from "@lib/map/render-objects"
import {
  type PartialElementParams_Entry as ElementEntry,
  type ElementIcon,
  PartialElementParams_ElementType as ElementType,
  PartialElementParamsSchema,
} from "@lib/proto/shared_pb"
import { configureStandardPagination } from "@lib/standard-pagination"
import { configureTagsFormat } from "@lib/tags-format"
import { setPageTitle } from "@lib/title"
import { memoize } from "@std/cache/memoize"
import { t } from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"
import { type ComponentChildren, render } from "preact"

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

const ELEMENTS_PER_PAGE = 15

export const getElementController = (map: MaplibreMap): IndexController => {
  const base = getBaseFetchController(map, "element", (sidebarSection) => {
    const sidebarContent = sidebarSection.querySelector("div.sidebar-content")!
    const sidebarTitleElement = sidebarContent.querySelector(".sidebar-title")!
    setPageTitle(sidebarTitleElement.textContent)

    // Handle not found
    if (!sidebarContent.dataset.params) return

    const [renderData, disposeElementContent] = initializeElementContent(
      map,
      sidebarContent,
    )
    const elements = convertRenderElementsData(renderData)
    focusObjects(map, elements, focusPaint)

    return () => {
      disposeElementContent()
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
  console.debug("Element: Initializing content")

  // Enhance tags table
  configureTagsFormat(container.querySelector("div.tags"))

  const locationButton = container.querySelector(".location-container button")
  locationButton?.addEventListener("click", () => {
    // On location click, pan the map
    const dataset = locationButton!.dataset
    console.debug("Element: Location clicked", dataset)
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
      renderElementsContainer(parentsContainer, params.parents, "parents"),
    )

  const membersContainer = container.querySelector("div.elements")
  if (membersContainer)
    disposeList.push(
      renderElementsContainer(
        membersContainer,
        params.members,
        ElementType[params.type] as "way" | "relation",
      ),
    )

  return [
    params.render!,
    () => {
      for (const dispose of disposeList) dispose()
    },
  ] as const
}

const renderElementsContainer = (
  elementsContainer: HTMLElement,
  elements: ElementEntry[],
  type: "way" | "relation" | "parents",
) => {
  console.debug("Element: Rendering component", elements.length)

  const titleElement = elementsContainer.querySelector(".title")!

  return configureElementsPagination(
    elementsContainer,
    elements,
    (page) => {
      titleElement.textContent = getElementsContainerTitle(type, elements.length, page)
    },
    (renderContainer, pageItems) =>
      render(
        pageItems.map((element) => (
          <ElementRow
            element={element}
            key={`${element.type}-${element.id}-${element.role ?? ""}`}
          />
        )),
        renderContainer,
      ),
  )
}

export const ElementsListRow = ({
  href,
  icon,
  title,
  meta,
  class: extraClass,
}: {
  href: string
  icon: ElementIcon | undefined
  title: ComponentChildren
  meta: ComponentChildren
  class?: string
}) => (
  <tr class={extraClass}>
    <td>
      {icon ? (
        <img
          loading="lazy"
          src={`/static/img/element/${icon.icon}`}
          title={icon.title}
          alt=""
          aria-hidden="true"
        />
      ) : null}
    </td>

    <td>
      <div class="element-row-title">
        <a href={href}>
          <bdi>{title}</bdi>
        </a>
      </div>
      <div class="element-row-meta">{meta}</div>
    </td>
  </tr>
)

const ElementRow = ({ element }: { element: ElementEntry }) => {
  const idStr = element.id.toString()
  const href = `/${ElementType[element.type]}/${idStr}`

  return (
    <ElementsListRow
      href={href}
      icon={element.icon}
      title={element.name || idStr}
      meta={
        <>
          <span>{getElementTypeLabel(element.type)}</span>
          {element.name && <span>{`#${idStr}`}</span>}
          {element.role && (
            <>
              <span
                class="element-row-meta-divider"
                aria-hidden="true"
              >
                ·
              </span>
              <span>{element.role}</span>
            </>
          )}
        </>
      }
    />
  )
}

const getElementsContainerTitle = (
  type: "way" | "relation" | "parents",
  elementsLength: number,
  page: number,
) => {
  const count = getPaginationCountLabel(page, elementsLength)

  if (type === "parents") {
    return `${t("browse.part_of")} (${count})`
  }
  if (type === "way") {
    // @ts-expect-error
    return t("browse.changeset.node", { count })
  }
  return `${t("browse.relation.members")} (${count})`
}

export const getElementTypeLabel = memoize((type: ElementType) => {
  if (type === ElementType.node) {
    return t("javascripts.query.node")
  }
  if (type === ElementType.way) {
    return t("javascripts.query.way")
  }
  return t("javascripts.query.relation")
})

export const configureElementsPagination = <T,>(
  container: HTMLElement,
  items: readonly T[],
  updateTitle: (page: number) => void,
  renderPage: (renderContainer: HTMLElement, pageItems: readonly T[]) => void,
) => {
  const paginationContainer = container.querySelector("ul.pagination")!
  const totalPages = Math.ceil(items.length / ELEMENTS_PER_PAGE)
  paginationContainer.dataset.pages = totalPages.toString()

  if (totalPages <= 1) {
    paginationContainer.parentElement!.classList.add("d-none")
  }

  return configureStandardPagination(container, {
    initialPage: 1,
    customLoader: (renderContainer: HTMLElement, page: number) => {
      const startIndex = (page - 1) * ELEMENTS_PER_PAGE
      const endIndex = Math.min(page * ELEMENTS_PER_PAGE, items.length)
      const pageItems = items.slice(startIndex, endIndex)

      updateTitle(page)
      renderPage(renderContainer, pageItems)
    },
  })
}

export const getPaginationCountLabel = (page: number, totalItems: number) => {
  if (totalItems > ELEMENTS_PER_PAGE) {
    const from = (page - 1) * ELEMENTS_PER_PAGE + 1
    const to = Math.min(page * ELEMENTS_PER_PAGE, totalItems)
    return t("pagination.range", {
      x: `${from}-${to}`,
      y: totalItems,
    })
  }
  return totalItems.toString()
}
