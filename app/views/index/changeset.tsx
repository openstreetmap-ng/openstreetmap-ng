import { fromBinary } from "@bufbuild/protobuf"
import { base64Decode } from "@bufbuild/protobuf/wire"
import { getBaseFetchController } from "@index/_base-fetch"
import {
  configureElementsPagination,
  ElementsListRow,
  getElementTypeLabel,
  getPaginationCountLabel,
} from "@index/element"
import type { IndexController } from "@index/router"
import { makeBoundsMinimumSize } from "@lib/map/bounds"
import {
  type DiffElement,
  hideDiff,
  parseOsmChange,
  showDiff,
} from "@lib/map/layers/diff-layer"
import { type FocusLayerPaint, focusObjects } from "@lib/map/layers/focus-layer"
import {
  type PartialChangesetParams_Element as Element,
  PartialElementParams_ElementType as ElementType,
  type PartialChangesetParams,
  PartialChangesetParamsSchema,
} from "@lib/proto/shared_pb"
import { configureReportButtons } from "@lib/report"
import { configureStandardForm } from "@lib/standard-form"
import { configureStandardPagination } from "@lib/standard-pagination"
import { configureTagsFormat } from "@lib/tags-format"
import { setPageTitle } from "@lib/title"
import type { Bounds, OSMChangeset } from "@lib/types"
import { t } from "i18next"
import type { MapLibreEvent, Map as MaplibreMap } from "maplibre-gl"
import { render } from "preact"

const focusPaint: FocusLayerPaint = {
  "fill-opacity": 0,
  "line-color": "#f90",
  "line-opacity": 1,
  "line-width": 3,
}

export const getChangesetController = (map: MaplibreMap) => {
  let params: PartialChangesetParams
  let paramsBounds: Bounds[]
  let diffElements: DiffElement[] | null = null
  let diffEnabled = false

  const base = getBaseFetchController(map, "changeset", (sidebarContent) => {
    configureTagsFormat(sidebarContent.querySelector("div.tags"))
    configureReportButtons(sidebarContent)

    const sidebarTitleElement =
      sidebarContent.querySelector<HTMLElement>(".sidebar-title")!
    const elementsSection = sidebarContent.querySelector("div.elements")!
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

    // Configure diff button
    const diffButton = sidebarContent.querySelector<HTMLButtonElement>(".diff-toggle-btn")
    if (diffButton) {
      diffButton.addEventListener("click", () => toggleDiff(diffButton))
    }

    return () => {
      disposeElements()
      disposePagination()
      map.off("zoomend", refocus)
      focusObjects(map)
      hideDiff(map)
      diffEnabled = false
      diffElements = null
    }
  })

  const refocus = (e?: MapLibreEvent) => {
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

  const toggleDiff = async (button: HTMLButtonElement) => {
    diffEnabled = !diffEnabled
    button.classList.toggle("active", diffEnabled)

    if (diffEnabled) {
      // Fetch and show diff if not already loaded
      if (!diffElements) {
        button.disabled = true
        try {
          const response = await fetch(`/api/0.6/changeset/${params.id}/download`)
          if (response.ok) {
            const xml = await response.text()
            diffElements = parseOsmChange(xml)
            console.debug("Changeset: Loaded diff with", diffElements.length, "elements")
          }
        } catch (error) {
          console.error("Changeset: Failed to load diff", error)
        }
        button.disabled = false
      }
      if (diffElements) {
        showDiff(map, diffElements)
      }
    } else {
      hideDiff(map)
    }
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

const renderElements = (
  elementsSection: HTMLElement,
  elements: {
    node: Element[]
    way: Element[]
    relation: Element[]
  },
) => {
  console.debug("Changeset: Rendering elements")

  const fragment = document.createDocumentFragment()
  const disposeList: (() => void)[] = []

  const groups = [
    [ElementType.node, elements.node],
    [ElementType.way, elements.way],
    [ElementType.relation, elements.relation],
  ] as const

  for (const [type, typeElements] of groups) {
    if (!typeElements.length) continue
    const groupContainer = document.createElement("div")
    fragment.appendChild(groupContainer)
    render(
      <ChangesetElementsGroup
        title={getElementsGroupTitle(type, typeElements.length, 1)}
      />,
      groupContainer,
    )
    disposeList.push(renderElementsGroup(groupContainer, type, typeElements))
  }

  if (fragment.children.length) {
    elementsSection.replaceChildren(fragment)
  } else {
    elementsSection.remove()
  }

  return () => {
    for (const dispose of disposeList) dispose()
  }
}

const renderElementsGroup = (
  groupContainer: HTMLElement,
  type: ElementType,
  elements: Element[],
) => {
  console.debug("Changeset: Rendering elements group", type, elements.length)

  const titleElement = groupContainer.querySelector(".title")!

  return configureElementsPagination(
    groupContainer,
    elements,
    (page) => {
      titleElement.textContent = getElementsGroupTitle(type, elements.length, page)
    },
    (renderContainer, pageItems) => {
      render(
        pageItems.map((element) => (
          <ChangesetElementRow
            element={element}
            type={type}
            key={`${type}-${element.id}-${element.version}`}
          />
        )),
        renderContainer,
      )
    },
  )
}

const ChangesetElementsGroup = ({ title }: { title: string }) => (
  <>
    <h4 class="title mt-3">{title}</h4>
    <div class="elements-list mb-2">
      <table>
        <tbody />
      </table>
    </div>
    <nav aria-label={t("alt.elements_page_navigation")}>
      <ul class="pagination pagination-sm pagination-2ch justify-content-end mb-0" />
    </nav>
  </>
)

const ChangesetElementRow = ({
  element,
  type,
}: {
  element: Element
  type: ElementType
}) => {
  const idStr = element.id.toString()
  const versionStr = element.version.toString()
  const typeSlug = ElementType[type]
  const hrefLatest = `/${typeSlug}/${idStr}`
  const hrefVersion = `/${typeSlug}/${idStr}/history/${versionStr}`
  return (
    <ElementsListRow
      href={hrefLatest}
      icon={element.icon}
      class={element.visible ? "" : "deleted"}
      title={element.name || idStr}
      meta={
        <>
          <span>{getElementTypeLabel(type)}</span>
          {element.name && <span>{`#${idStr}`}</span>}
          <span
            class="element-row-meta-divider"
            aria-hidden="true"
          >
            ·
          </span>
          <a href={hrefVersion}>{`v${versionStr}`}</a>
        </>
      }
    />
  )
}

const getElementsGroupTitle = (
  type: ElementType,
  elementsLength: number,
  page: number,
) => {
  const count = getPaginationCountLabel(page, elementsLength)

  if (type === ElementType.node) {
    // @ts-expect-error
    return t("browse.changeset.node", { count })
  }
  if (type === ElementType.way) {
    // @ts-expect-error
    return t("browse.changeset.way", { count })
  }
  // @ts-expect-error
  return t("browse.changeset.relation", { count })
}
