import { fromBinary } from "@bufbuild/protobuf"
import { getActionSidebar, switchActionSidebar } from "@index/_action-sidebar"
import type { RouteLoadReason } from "@index/router"
import { routerNavigateStrict } from "@index/router"
import { darkenColor } from "@lib/color"
import { Time } from "@lib/datetime-inputs"
import { tRich } from "@lib/i18n"
import {
  checkLngLatBoundsIntersection,
  getLngLatBoundsIntersection,
  getLngLatBoundsSize,
  lngLatBoundsEqual,
  makeBoundsMinimumSize,
  padLngLatBounds,
  unionBounds,
} from "@lib/map/bounds"
import { clearMapHover, setMapHover } from "@lib/map/hover"
import {
  addMapLayer,
  emptyFeatureCollection,
  getExtendedLayerId,
  type LayerId,
  layersConfig,
  removeMapLayer,
} from "@lib/map/layers/layers.ts"
import { convertRenderChangesetsData, renderObjects } from "@lib/map/render-objects.ts"
import { requestAnimationFramePolyfill } from "@lib/polyfills"
import {
  type RenderChangesetsData_Changeset,
  type RenderChangesetsData_Changeset_User,
  RenderChangesetsDataSchema,
} from "@lib/proto/shared_pb"
import { qsEncode, qsParse } from "@lib/qs"
import { setPageTitle } from "@lib/title"
import type { Bounds, OSMChangeset } from "@lib/types"
import { assert } from "@std/assert"
import { delay } from "@std/async/delay"
import { throttle } from "@std/async/unstable-throttle"
import { SECOND } from "@std/datetime/constants"
import type { GeoJsonProperties } from "geojson"
import { t } from "i18next"
import {
  type GeoJSONSource,
  LngLatBounds,
  type MapGeoJSONFeature,
  type Map as MaplibreMap,
} from "maplibre-gl"
import { type ComponentChild, render } from "preact"

const FADE_SPEED = 0.2
const THICKNESS_SPEED = FADE_SPEED * 0.6
const LINE_WIDTH = 3

const LAYER_ID = "changesets-history" as LayerId
const LAYER_ID_BORDERS = "changesets-history-borders" as LayerId

layersConfig.set(LAYER_ID_BORDERS, {
  specification: {
    type: "geojson",
    data: emptyFeatureCollection,
  },
  layerTypes: ["line"],
  layerOptions: {
    layout: {
      "line-cap": "round",
      "line-join": "round",
    },
    paint: {
      "line-color": "#fff",
      "line-opacity": 1,
      "line-width": [
        "case",
        ["boolean", ["feature-state", "hover"], false],
        ["feature-state", "scrollBorderWidthHover"],
        ["coalesce", ["feature-state", "scrollBorderWidth"], 0],
      ],
    },
  },
  priority: 120,
})

layersConfig.set(LAYER_ID, {
  specification: {
    type: "geojson",
    data: emptyFeatureCollection,
  },
  layerTypes: ["fill", "line"],
  layerOptions: {
    layout: {
      "line-cap": "round",
      "line-join": "round",
    },
    paint: {
      "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 0.35, 0],
      "fill-color": "#ffc",
      "line-color": [
        "case",
        ["boolean", ["feature-state", "hover"], false],
        ["feature-state", "scrollColorHover"],
        ["feature-state", "scrollColor"],
      ],
      "line-opacity": [
        "case",
        ["boolean", ["feature-state", "hover"], false],
        ["feature-state", "scrollOpacityHover"],
        ["feature-state", "scrollOpacity"],
      ],
      "line-width": [
        "case",
        ["boolean", ["feature-state", "hover"], false],
        ["feature-state", "scrollWidthHover"],
        ["coalesce", ["feature-state", "scrollWidth"], 0],
      ],
    },
  },
  priority: 121,
})

const FOCUS_HOVER_DELAY = 1 * SECOND
const LOAD_MORE_SCROLL_BUFFER = 1000
const RELOAD_PROPORTION_THRESHOLD = 0.9

const distanceOpacity = (distance: number) => Math.max(1 - distance * FADE_SPEED, 0)

const pickSmallestBoundsFeature = (features: MapGeoJSONFeature[]) =>
  features.reduce((a, b) =>
    a.properties.boundsArea <= b.properties.boundsArea ? a : b,
  )

export const getChangesetsHistoryController = (map: MaplibreMap) => {
  const source = map.getSource<GeoJSONSource>(LAYER_ID)!
  const sourceBorders = map.getSource<GeoJSONSource>(LAYER_ID_BORDERS)!
  const sidebar = getActionSidebar("changesets-history")
  const parentSidebar = sidebar.closest("div.sidebar")!
  const sidebarTitleElement = sidebar.querySelector(".sidebar-title")!
  const dateFilterElement = sidebar.querySelector(".date-filter")!
  const entryContainer = sidebar.querySelector("ul.changesets-list")!
  const loadingContainer = sidebar.querySelector(".loading")!
  const scrollIndicators = sidebar.querySelectorAll(".scroll-indicator")

  let abortController: AbortController | undefined

  // Store changesets to allow loading more
  const changesets: RenderChangesetsData_Changeset[] = []
  let fetchedBounds: LngLatBounds | null = null
  let fetchedDate: string | undefined
  let renderedDateFilter: string | undefined
  let noMoreChangesets = false
  let loadScope: string | undefined
  let loadDisplayName: string | undefined
  const idChangesetMap = new Map<string, RenderChangesetsData_Changeset>()
  const idFirstFeatureIdMap = new Map<string, number>()
  const idSidebarMap = new Map<string, HTMLLIElement>()
  let visibleChangesetsBounds: LngLatBounds | null = null
  let hiddenBefore = 0
  let hiddenAfter = 0
  let sidebarHoverAbort: AbortController | undefined
  let sidebarHoverId: string | null = null
  let shouldFitOnInitialLoad = false
  let hoveredChangesetId: string | null = null
  let renderedChangesetsCount = 0
  let removeEntryHoverHandlers: (() => void) | null = null

  const cancelSidebarHoverFit = () => {
    sidebarHoverAbort?.abort()
    sidebarHoverId = null
  }

  const changesetIsWithinView = (changesetId: string) => {
    const cs = idChangesetMap.get(changesetId)
    if (!cs) return false
    const mapBounds = map.getBounds()
    return cs.bounds.some((b) => {
      const csBounds = new LngLatBounds([b.minLon, b.minLat, b.maxLon, b.maxLat])
      return checkLngLatBoundsIntersection(mapBounds, csBounds)
    })
  }

  const scheduleSidebarFit = async (changesetId: string) => {
    sidebarHoverAbort?.abort()
    sidebarHoverAbort = new AbortController()
    sidebarHoverId = changesetId

    try {
      await delay(FOCUS_HOVER_DELAY, { signal: sidebarHoverAbort.signal })
    } catch {
      return
    }

    if (
      // Ensure the item is currently rendered in the map layers
      !idFirstFeatureIdMap.has(changesetId) ||
      changesetIsWithinView(changesetId) ||
      !visibleChangesetsBounds
    )
      return

    console.debug("ChangesetsHistory: Fitting after hover")
    map.fitBounds(
      padLngLatBounds(visibleChangesetsBounds, 0.3),
      { maxZoom: 16 },
      { skipUpdateState: true },
    )
  }

  const clearSidebar = () => {
    for (const element of idSidebarMap.values()) render(null, element)
    idSidebarMap.clear()
    entryContainer.replaceChildren()
    renderedChangesetsCount = 0
  }

  const resetChangesets = () => {
    console.debug("ChangesetsHistory: Reset")
    onMapMouseLeave()
    source.setData(emptyFeatureCollection)
    sourceBorders.setData(emptyFeatureCollection)
    changesets.length = 0
    noMoreChangesets = false
    idChangesetMap.clear()
    idFirstFeatureIdMap.clear()
    visibleChangesetsBounds = null
    cancelSidebarHoverFit()
    hiddenBefore = 0
    hiddenAfter = 0
    hoveredChangesetId = null
    clearSidebar()
    for (const indicator of scrollIndicators) {
      indicator.classList.add("d-none")
    }
  }

  /** Update changeset visibility states */
  const updateLayersVisibility = () => {
    const sidebarRect = parentSidebar.getBoundingClientRect()
    const sidebarTop = sidebarRect.top
    const sidebarBottom = sidebarRect.bottom

    let newHiddenBefore = 0
    let newHiddenAfter = 0
    let foundVisible = false
    const updateFeatureStates: [
      string,
      number,
      "above" | "visible" | "below",
      number,
    ][] = []

    for (let i = changesets.length - 1; i >= 0; i--) {
      const changeset = changesets[i]
      const changesetId = changeset.id.toString()
      const numBounds = changeset.bounds.length
      const element = idSidebarMap.get(changesetId)
      if (!element) continue
      const elementRect = element.getBoundingClientRect()
      const elementTop = elementRect.top
      const elementBottom = elementRect.bottom

      let state: "above" | "visible" | "below"
      let distance = 0
      let hidden = false

      if (elementBottom < sidebarTop) {
        state = "above"
        distance = (sidebarTop - elementBottom) / sidebarRect.height
      } else if (elementTop > sidebarBottom) {
        state = "below"
        distance = (elementTop - sidebarBottom) / sidebarRect.height
      } else {
        state = "visible"
        distance = 0
      }

      if (state !== "visible") {
        const opacity = distanceOpacity(distance)
        hidden = opacity < 0.05
      }

      if (!foundVisible && hidden) {
        newHiddenAfter++
      } else if (!hidden) {
        foundVisible = true
      } else if (foundVisible && hidden) {
        newHiddenBefore = i + 1
        break
      }

      if (!hidden) updateFeatureStates.push([changesetId, numBounds, state, distance])
    }

    if (newHiddenBefore !== hiddenBefore || newHiddenAfter !== hiddenAfter) {
      hiddenBefore = newHiddenBefore
      hiddenAfter = newHiddenAfter
      updateLayers()
    }

    for (const [changesetId, numBounds, state, distance] of updateFeatureStates)
      updateFeatureState(changesetId, numBounds, state, distance)
  }

  const throttledUpdateLayersVisibility = throttle(updateLayersVisibility, 50, {
    ensureLastCall: true,
  })

  /** Update changeset visibility and calculate consecutive hidden ranges */
  const updateFeatureState = (
    changesetId: string,
    numBounds: number,
    state: "above" | "visible" | "below",
    distance: number,
  ) => {
    const firstFeatureId = idFirstFeatureIdMap.get(changesetId)
    if (!firstFeatureId) return

    let color: string
    let colorHover: string
    let opacity: number
    let width: number
    let widthHover: number

    if (state === "visible") {
      color = "#f90"
      colorHover = "#f60"
      opacity = 1
      width = LINE_WIDTH
      widthHover = width + 2
    } else {
      color =
        state === "above"
          ? "#ed59e4" // ~40% lighten
          : "#14B8A6"
      colorHover = darkenColor(color, 0.15)
      opacity = distanceOpacity(distance)
      width = Math.max(LINE_WIDTH - distance * THICKNESS_SPEED * LINE_WIDTH, 0)
      widthHover = Math.max(width, 1) + 2
    }

    const borderWidthHover = widthHover + 2.5
    const featureState = {
      scrollColor: color,
      scrollColorHover: colorHover,
      scrollOpacity: opacity,
      scrollOpacityHover: 1,
      scrollWidth: width,
      scrollWidthHover: widthHover,
      scrollBorderWidth: 0,
      scrollBorderWidthHover: borderWidthHover,
    }

    for (let i = firstFeatureId; i < firstFeatureId + numBounds * 2; i++) {
      map.setFeatureState({ source: LAYER_ID_BORDERS, id: i }, featureState)
      map.setFeatureState({ source: LAYER_ID, id: i }, featureState)
    }
  }

  const updateLayers = (e?: any) => {
    let featureIdCounter = 1
    for (let i = 0; i < hiddenBefore; i++)
      featureIdCounter += changesets[i].bounds.length * 2

    idFirstFeatureIdMap.clear()
    const changesetsMinimumSize: OSMChangeset[] = []
    let aggregatedBounds: Bounds | undefined

    let firstFeatureId = featureIdCounter
    for (const changeset of convertRenderChangesetsData(
      changesets.slice(hiddenBefore, changesets.length - hiddenAfter),
    )) {
      idFirstFeatureIdMap.set(changeset.id.toString(), firstFeatureId)
      firstFeatureId += changeset.bounds.length * 2

      changeset.bounds = changeset.bounds.map((bounds) => {
        const resized = makeBoundsMinimumSize(map, bounds)
        aggregatedBounds = unionBounds(aggregatedBounds, resized)
        return resized
      })
      changesetsMinimumSize.push(changeset)
    }

    visibleChangesetsBounds = aggregatedBounds
      ? new LngLatBounds(aggregatedBounds)
      : null

    const data = renderObjects(changesetsMinimumSize, { featureIdCounter })
    source.setData(data)
    sourceBorders.setData(data)

    // Update layers visibility after map event
    if (e) updateLayersVisibility()

    // When initial loading for scope/user, focus on the changesets
    if (!e && shouldFitOnInitialLoad && visibleChangesetsBounds && !idSidebarMap.size) {
      console.debug("ChangesetsHistory: Fitting to changesets")
      map.fitBounds(
        padLngLatBounds(visibleChangesetsBounds, 0.3),
        { maxZoom: 16, animate: false },
        { skipUpdateState: true },
      )
    }
  }

  const handleEntryMouseEnter = (changesetId: string) => {
    const changeset = idChangesetMap.get(changesetId)
    if (!changeset) return
    scheduleSidebarFit(changesetId)
    if (hoveredChangesetId && hoveredChangesetId !== changesetId) {
      const prevChangeset = idChangesetMap.get(hoveredChangesetId)
      if (prevChangeset)
        setHover(
          {
            id: hoveredChangesetId,
            numBounds: prevChangeset.bounds.length,
          },
          false,
        )
    }
    setHover({ id: changesetId, numBounds: changeset.bounds.length }, true)
    hoveredChangesetId = changesetId
  }

  const handleEntryMouseLeave = (changesetId: string) => {
    if (sidebarHoverId === changesetId) cancelSidebarHoverFit()
    const changeset = idChangesetMap.get(changesetId)
    if (changeset)
      setHover({ id: changesetId, numBounds: changeset.bounds.length }, false)
    if (hoveredChangesetId === changesetId) hoveredChangesetId = null
  }

  const updateSidebar = () => {
    const createdText = t("browse.created").toLowerCase()
    const closedText = t("browse.closed").toLowerCase()
    const noCommentText = t("browse.no_comment")

    const fragment = document.createDocumentFragment()

    for (let i = renderedChangesetsCount; i < changesets.length; i++) {
      const changeset = changesets[i]
      const changesetId = changeset.id.toString()
      if (idSidebarMap.has(changesetId)) continue

      const element = document.createElement("li")
      element.className = "social-entry clickable"
      element.dataset.changesetId = changesetId
      idSidebarMap.set(changesetId, element)
      const hasComments = changeset.numComments > 0n
      render(
        <>
          <p class="header text-muted d-flex justify-content-between">
            <span>
              <span class="user me-1">{renderUser(changeset.user)}</span>
              <span class="date">
                {changeset.closed ? closedText : createdText}{" "}
                <Time
                  unix={changeset.timeago}
                  relativeStyle="long"
                />
              </span>
            </span>
            <a
              class="stretched-link"
              href={`/changeset/${changesetId}`}
            >
              {changesetId}
            </a>
          </p>
          <div class="body">
            <div class="d-flex justify-content-between">
              <div class="comment">{changeset.comment || noCommentText}</div>
              <div class={`num-comments ${hasComments ? "" : "no-comments"}`}>
                {changeset.numComments.toString()}
                <i class={`bi ${hasComments ? "bi-chat-left-text" : "bi-chat-left"}`} />
              </div>
            </div>
            <div class="changeset-stats">
              {changeset.numCreate > 0 && (
                <span class="stat-create">{changeset.numCreate}</span>
              )}
              {changeset.numModify > 0 && (
                <span class="stat-modify">{changeset.numModify}</span>
              )}
              {changeset.numDelete > 0 && (
                <span class="stat-delete">{changeset.numDelete}</span>
              )}
            </div>
          </div>
        </>,
        element,
      )
      fragment.append(element)
    }

    renderedChangesetsCount = changesets.length
    entryContainer.append(fragment)
  }

  const addEntryHoverHandlers = () => {
    if (removeEntryHoverHandlers) return
    const getEntryFromEvent = (event: MouseEvent) => {
      const target = event.target
      const element =
        target instanceof Element
          ? target
          : target instanceof Node
            ? target.parentElement
            : null
      if (!element) return null
      const entry = element.closest("li[data-changeset-id]")
      if (!(entry instanceof HTMLLIElement)) return null
      return entry
    }

    const handleHover = (event: MouseEvent, hover: boolean) => {
      const entry = getEntryFromEvent(event)
      const changesetId = entry?.dataset.changesetId
      if (!changesetId) return

      if (event.relatedTarget instanceof Node && entry.contains(event.relatedTarget))
        return

      if (hover) handleEntryMouseEnter(changesetId)
      else handleEntryMouseLeave(changesetId)
    }

    const onMouseOver = (event: MouseEvent) => handleHover(event, true)
    const onMouseOut = (event: MouseEvent) => handleHover(event, false)

    entryContainer.addEventListener("mouseover", onMouseOver)
    entryContainer.addEventListener("mouseout", onMouseOut)

    removeEntryHoverHandlers = () => {
      entryContainer.removeEventListener("mouseover", onMouseOver)
      entryContainer.removeEventListener("mouseout", onMouseOut)
      removeEntryHoverHandlers = null
    }
  }

  const setHover = (
    properties: GeoJsonProperties,
    hover: boolean,
    scrollIntoView = false,
  ) => {
    const { id, numBounds } = properties!
    const result = idSidebarMap.get(id)
    result?.classList.toggle("hover", hover)

    if (hover && scrollIntoView && result)
      result.scrollIntoView({ behavior: "smooth", block: "center" })

    const firstFeatureId = idFirstFeatureIdMap.get(id)
    if (!firstFeatureId) return
    for (let i = firstFeatureId; i < firstFeatureId + numBounds * 2; i++) {
      map.setFeatureState({ source: LAYER_ID_BORDERS, id: i }, { hover })
      map.setFeatureState({ source: LAYER_ID, id: i }, { hover })
    }
  }

  const LAYER_IDFill = getExtendedLayerId(LAYER_ID, "fill")

  map.on("click", LAYER_IDFill, (e) => {
    const feature = pickSmallestBoundsFeature(e.features!)
    const changesetId = feature.properties.id
    routerNavigateStrict(`/changeset/${changesetId}`)
  })

  let hoveredFeature: MapGeoJSONFeature | null = null
  let scrollDelayAbort: AbortController | undefined
  map.on("mousemove", LAYER_IDFill, async (e) => {
    const feature = pickSmallestBoundsFeature(e.features!)
    if (hoveredFeature) {
      if (hoveredFeature.id === feature.id) return
      setHover(hoveredFeature.properties, false)
    } else {
      setMapHover(map, LAYER_ID)
    }

    scrollDelayAbort?.abort()
    scrollDelayAbort = new AbortController()
    hoveredFeature = feature
    setHover(hoveredFeature.properties, true)

    // Set delayed scroll
    try {
      await delay(FOCUS_HOVER_DELAY, { signal: scrollDelayAbort.signal })
    } catch {
      return
    }

    setHover(hoveredFeature!.properties, true, true)
  })

  const onMapMouseLeave = () => {
    if (!hoveredFeature) return
    scrollDelayAbort?.abort()
    setHover(hoveredFeature.properties, false)
    hoveredFeature = null
    clearMapHover(map, LAYER_ID)
  }
  map.on("mouseleave", LAYER_IDFill, onMapMouseLeave)

  const onSidebarScroll = () => {
    // Update changeset visibility based on scroll position
    throttledUpdateLayersVisibility()

    // Load more changesets if scrolled to bottom
    if (
      noMoreChangesets ||
      parentSidebar.offsetHeight + parentSidebar.scrollTop <
        parentSidebar.scrollHeight - LOAD_MORE_SCROLL_BUFFER
    )
      return
    console.debug("ChangesetsHistory: Scrolled to bottom")
    updateState()
  }

  /** On map update, fetch the changesets in view and update the changesets layer */
  const updateState = async (e?: any) => {
    if (e?.skipUpdateState) return

    // Request full world when initial loading for scope/user
    const fetchBounds =
      fetchedBounds || !(loadScope || loadDisplayName) ? map.getBounds() : null

    // During full world view, skip event-based updates
    if (e && !fetchBounds) {
      return
    }

    const params: Record<string, string | undefined> = qsParse(window.location.search)

    // Update date filter element
    const fetchDate = params.date
    if (fetchDate !== renderedDateFilter) {
      renderedDateFilter = fetchDate
      if (fetchDate) {
        const textSpan = document.createElement("span")
        textSpan.textContent = t("changeset.viewing_edits_from_date", {
          date: fetchDate,
        })
        textSpan.classList.add("date-filter-text")

        const closeLink = document.createElement("a")
        closeLink.href = `${window.location.pathname}${qsEncode({
          ...params,
          date: undefined,
        })}`
        closeLink.classList.add("btn", "btn-sm", "btn-link", "btn-close")
        closeLink.title = t("action.remove_filter")
        dateFilterElement.replaceChildren(textSpan, closeLink)
      } else {
        dateFilterElement.replaceChildren()
      }
    }

    if (lngLatBoundsEqual(fetchedBounds, fetchBounds) && fetchedDate === fetchDate) {
      // Load more changesets
      if (noMoreChangesets) return
      if (changesets.length) params.before = changesets.at(-1)!.id.toString()
    } else {
      // Ignore small bounds changes
      if (fetchedBounds && fetchBounds && fetchedDate === fetchDate) {
        const visibleBounds = getLngLatBoundsIntersection(fetchedBounds, fetchBounds)
        const visibleArea = getLngLatBoundsSize(visibleBounds)
        const fetchArea = getLngLatBoundsSize(fetchBounds)
        const proportion =
          visibleArea / Math.max(getLngLatBoundsSize(fetchedBounds), fetchArea)
        if (proportion > RELOAD_PROPORTION_THRESHOLD) return
      }

      // Clear the changesets if the bbox changed
      resetChangesets()
    }
    if (fetchBounds) {
      const [[minLon, minLat], [maxLon, maxLat]] = fetchBounds
        .adjustAntiMeridian()
        .toArray()
      params.bbox = `${minLon},${minLat},${maxLon},${maxLat}`
    }

    params.scope = loadScope
    params.display_name = loadDisplayName

    loadingContainer.classList.remove("d-none")
    parentSidebar.removeEventListener("scroll", onSidebarScroll)

    // Abort any pending request
    abortController?.abort()
    abortController = new AbortController()
    const signal = abortController.signal

    try {
      const resp = await fetch(`/api/web/changeset/map${qsEncode(params)}`, {
        signal: signal,
        priority: "high",
      })
      assert(resp.ok, `${resp.status} ${resp.statusText}`)

      const buffer = await resp.arrayBuffer()
      const newChangesets = fromBinary(
        RenderChangesetsDataSchema,
        new Uint8Array(buffer),
      ).changesets

      if (newChangesets.length) {
        changesets.push(...newChangesets)
        for (const cs of newChangesets) {
          idChangesetMap.set(cs.id.toString(), cs)
        }
        console.debug(
          "ChangesetsHistory: Loaded",
          changesets.length,
          "changesets,",
          newChangesets.length,
          "new",
        )
        updateLayers()
        updateSidebar()
        requestAnimationFramePolyfill(updateLayersVisibility)
      } else {
        console.debug("ChangesetsHistory: No more changesets")
        noMoreChangesets = true
      }

      fetchedBounds = fetchBounds
      fetchedDate = fetchDate

      if (changesets.length)
        for (const indicator of scrollIndicators) indicator.classList.remove("d-none")
    } catch (error) {
      if (error.name === "AbortError") return
      console.error("ChangesetsHistory: Failed to fetch", error)
      resetChangesets()
    } finally {
      if (!signal.aborted) {
        loadingContainer.classList.add("d-none")
        parentSidebar.addEventListener("scroll", onSidebarScroll)
      }
    }
  }

  return {
    load: (
      { scope, displayName }: { scope?: string; displayName?: string },
      reason?: RouteLoadReason,
    ) => {
      loadScope = scope
      loadDisplayName = displayName
      shouldFitOnInitialLoad = reason === "navigation" && Boolean(scope || displayName)

      switchActionSidebar(map, sidebar)
      // TODO: handle scope
      let sidebarTitle: ComponentChild
      let sidebarTitleText: string
      if (displayName) {
        const userLink = <a href={`/user/${displayName}`}>{displayName}</a>
        sidebarTitle = tRich("changesets.index.title_user", {
          user: userLink,
        })
        sidebarTitleText = t("changesets.index.title_user", {
          user: displayName,
        })
      } else if (scope === "nearby") {
        const title = t("changesets.index.title_nearby")
        sidebarTitle = title
        sidebarTitleText = title
      } else if (scope === "friends") {
        const title = t("changesets.index.title_friend")
        sidebarTitle = title
        sidebarTitleText = title
      } else {
        const title = t("changesets.index.title")
        sidebarTitle = title
        sidebarTitleText = title
      }
      render(sidebarTitle, sidebarTitleElement)
      setPageTitle(sidebarTitleText)

      addEntryHoverHandlers()

      addMapLayer(map, LAYER_ID)
      addMapLayer(map, LAYER_ID_BORDERS)
      map.on("zoomend", updateLayers)
      map.on("moveend", updateState)
      updateState()
    },
    unload: () => {
      map.off("moveend", updateState)
      map.off("zoomend", updateLayers)
      parentSidebar.removeEventListener("scroll", onSidebarScroll)
      removeEntryHoverHandlers?.()
      removeMapLayer(map, LAYER_ID)
      removeMapLayer(map, LAYER_ID_BORDERS)
      resetChangesets()
      fetchedBounds = null
    },
  }
}

const renderUser = (user: RenderChangesetsData_Changeset_User | undefined) => {
  if (!user) return t("browse.anonymous")

  return (
    <a href={`/user/${user.name}`}>
      <img
        class="avatar"
        src={user.avatarUrl}
        alt={t("alt.profile_picture")}
        loading="lazy"
      />
      {user.name}
    </a>
  )
}
