import { fromBinary } from "@bufbuild/protobuf"
import { LoadingSpinner, SidebarHeader } from "@index/_action-sidebar"
import { ChangesetRoute, ChangesetStats } from "@index/changeset"
import { defineRoute, routerCtx, routerNavigate } from "@index/router"
import { queryParam, routeParam } from "@lib/codecs"
import { darkenColor } from "@lib/color"
import { Time } from "@lib/datetime-inputs"
import { type Scheduled, useDisposeEffect } from "@lib/dispose-scope"
import { tRich } from "@lib/i18n"
import {
  boundsEqual,
  boundsIntersect,
  boundsIntersection,
  boundsPadding,
  boundsSize,
  boundsToString,
  boundsUnion,
  makeBoundsMinimumSize,
} from "@lib/map/bounds"
import { clearMapHover, setMapHover } from "@lib/map/hover"
import {
  emptyFeatureCollection,
  getExtendedLayerId,
  type LayerId,
  layersConfig,
} from "@lib/map/layers/layers.ts"
import { convertRenderChangesetsData, renderObjects } from "@lib/map/render-objects.ts"
import {
  type RenderChangesetsData_Changeset,
  RenderChangesetsDataSchema,
} from "@lib/proto/shared_pb"
import { qsEncode } from "@lib/qs"
import { scrollElementIntoView } from "@lib/scroll"
import { setPageTitle } from "@lib/title"
import type { Bounds, OSMChangeset } from "@lib/types"
import {
  batch,
  type ReadonlySignal,
  useComputed,
  useSignal,
  useSignalEffect,
} from "@preact/signals"
import { assert } from "@std/assert"
import { delay } from "@std/async/delay"
import { minBy } from "@std/collections/min-by"
import { SECOND } from "@std/datetime/constants"
import { t } from "i18next"
import {
  type GeoJSONSource,
  LngLatBounds,
  type MapGeoJSONFeature,
  type MapLayerMouseEvent,
  type Map as MaplibreMap,
} from "maplibre-gl"
import { useEffect, useRef } from "preact/hooks"

// --- Constants ---

const FADE_SPEED = 0.2
const THICKNESS_SPEED = FADE_SPEED * 0.6
const LINE_WIDTH = 3
const FOCUS_HOVER_DELAY = 1 * SECOND
const LOAD_MORE_SCROLL_BUFFER = 1000
const RELOAD_PROPORTION_THRESHOLD = 0.9

// --- Layer Configuration ---

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

const distanceOpacity = (distance: number) => Math.max(1 - distance * FADE_SPEED, 0)

const pickSmallestBoundsFeature = (features: MapGeoJSONFeature[]) =>
  minBy(features, (f) => f.properties.boundsArea)!

const ChangesetsHistorySidebar = ({
  map,
  date,
  scope,
  displayName,
}: {
  map: MaplibreMap
  date: ReadonlySignal<string | undefined>
  scope: ReadonlySignal<"nearby" | "friends" | undefined>
  displayName: ReadonlySignal<string | undefined>
}) => {
  const changesets = useSignal<RenderChangesetsData_Changeset[]>([])
  const loading = useSignal(false)
  const noMoreChangesets = useSignal(false)
  const hoveredChangesetId = useSignal<string | null>(null)
  const showScrollTop = useSignal(false)
  const showScrollBottom = useSignal(false)

  const sidebarTitle = useComputed(() => {
    const dn = displayName.value
    const sc = scope.value
    if (dn)
      return {
        html: tRich("changesets.index.title_user", {
          user: () => <a href={`/user/${dn}`}>{dn}</a>,
        }),
        plain: t("changesets.index.title_user", { user: dn }),
      }
    let title: string
    if (sc === "nearby") title = t("changesets.index.title_nearby")
    else if (sc === "friends") title = t("changesets.index.title_friend")
    else title = t("changesets.index.title")
    return { html: title, plain: title }
  })

  setPageTitle(sidebarTitle.value.plain)

  // Refs - DOM
  const parentSidebar = document
    .getElementById("ActionSidebar")!
    .closest("div.sidebar")!
  const loadMoreSentinel = useRef<HTMLDivElement>(null)

  // Refs - Data mappings
  const idSidebarMap = useRef(new Map<string, HTMLLIElement>())
  const idChangesetMap = useRef(new Map<string, RenderChangesetsData_Changeset>())
  const idFirstFeatureIdMap = useRef(new Map<string, number>())

  // Refs - Fetch state
  const fetchAbort = useRef<AbortController | null>(null)
  const fetchedContext = useRef<{
    bounds: LngLatBounds | null
    date: string | undefined
    scope: "nearby" | "friends" | undefined
    displayName: string | undefined
  }>({ bounds: null, date: undefined, scope: undefined, displayName: undefined })

  // Refs - Visibility tracking
  const hiddenBefore = useRef(0)
  const hiddenAfter = useRef(0)
  const visibleChangesetsBounds = useRef<LngLatBounds | null>(null)

  // Refs - Hover/interaction state
  const hoveredFeature = useRef<MapGeoJSONFeature | null>(null)
  const sidebarHoverAbort = useRef<AbortController | null>(null)
  const scrollDelayAbort = useRef<AbortController | null>(null)
  const scheduleLayersVisibilityUpdateFn = useRef<Scheduled<() => void> | null>(null)
  const scheduleCheckLoadMoreFn = useRef<Scheduled<() => void> | null>(null)

  // --- Core Functions ---

  const resetChangesets = () => {
    fetchAbort.current?.abort()
    onMapMouseLeave()
    batch(() => {
      changesets.value = []
      loading.value = false
      noMoreChangesets.value = false
      hoveredChangesetId.value = null
      showScrollTop.value = false
      showScrollBottom.value = false
    })
    fetchedContext.current = {
      bounds: null,
      date: undefined,
      scope: undefined,
      displayName: undefined,
    }
    idChangesetMap.current.clear()
    idFirstFeatureIdMap.current.clear()
    idSidebarMap.current.clear()
    visibleChangesetsBounds.current = null
    hiddenBefore.current = 0
    hiddenAfter.current = 0
    sidebarHoverAbort.current?.abort()
  }

  const updateFeatureState = (
    changesetId: string,
    numBounds: number,
    state: "above" | "visible" | "below",
    distance: number,
  ) => {
    const firstFeatureId = idFirstFeatureIdMap.current.get(changesetId)
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
      color = state === "above" ? "#ed59e4" : "#14B8A6"
      colorHover = darkenColor(color, 0.15)
      opacity = distanceOpacity(distance)
      width = Math.max(LINE_WIDTH - distance * THICKNESS_SPEED * LINE_WIDTH, 0)
      widthHover = Math.max(width, 1) + 2
    }

    const featureState = {
      scrollColor: color,
      scrollColorHover: colorHover,
      scrollOpacity: opacity,
      scrollOpacityHover: 1,
      scrollWidth: width,
      scrollWidthHover: widthHover,
      scrollBorderWidth: 0,
      scrollBorderWidthHover: widthHover + 2.5,
    }

    for (let i = firstFeatureId; i < firstFeatureId + numBounds * 2; i++) {
      map.setFeatureState({ source: LAYER_ID_BORDERS, id: i }, featureState)
      map.setFeatureState({ source: LAYER_ID, id: i }, featureState)
    }
  }

  const updateLayers = (isFirstLoad = false) => {
    const source = map.getSource<GeoJSONSource>(LAYER_ID)
    const sourceBorders = map.getSource<GeoJSONSource>(LAYER_ID_BORDERS)
    if (!(source && sourceBorders)) return

    const csList = changesets.value
    let featureIdCounter = 1
    for (let i = 0; i < hiddenBefore.current; i++)
      featureIdCounter += csList[i].bounds.length * 2

    idFirstFeatureIdMap.current.clear()
    const changesetsMinimumSize: OSMChangeset[] = []
    let aggregatedBounds: Bounds | undefined

    let firstFeatureId = featureIdCounter
    const visibleChangesets = csList.slice(
      hiddenBefore.current,
      csList.length - hiddenAfter.current,
    )

    for (const changeset of convertRenderChangesetsData(visibleChangesets)) {
      idFirstFeatureIdMap.current.set(changeset.id.toString(), firstFeatureId)
      firstFeatureId += changeset.bounds.length * 2

      changeset.bounds = changeset.bounds.map((bounds) => {
        const resized = makeBoundsMinimumSize(map, bounds)
        aggregatedBounds = boundsUnion(aggregatedBounds, resized)
        return resized
      })
      changesetsMinimumSize.push(changeset)
    }

    visibleChangesetsBounds.current = aggregatedBounds
      ? new LngLatBounds(aggregatedBounds)
      : null

    const data = renderObjects(changesetsMinimumSize, { featureIdCounter })
    source.setData(data)
    sourceBorders.setData(data)

    // Fit bounds on first load for scoped views (user/nearby/friends)
    const shouldFit =
      routerCtx.value.reason === "navigation" &&
      Boolean(scope.value || displayName.value)
    if (shouldFit && visibleChangesetsBounds.current && isFirstLoad)
      map.fitBounds(boundsPadding(visibleChangesetsBounds.current, 0.3), {
        maxZoom: 16,
        animate: false,
      })
  }

  type ScrollState = { state: "above" | "visible" | "below"; distance: number }

  const getElementScrollState = (
    elementRect: DOMRect,
    sidebarRect: DOMRect,
  ): ScrollState => {
    if (elementRect.bottom < sidebarRect.top) {
      return {
        state: "above",
        distance: (sidebarRect.top - elementRect.bottom) / sidebarRect.height,
      }
    }
    if (elementRect.top > sidebarRect.bottom) {
      return {
        state: "below",
        distance: (elementRect.top - sidebarRect.bottom) / sidebarRect.height,
      }
    }
    return { state: "visible", distance: 0 }
  }

  const updateScrollIndicators = (sidebarRect: DOMRect) => {
    batch(() => {
      const csList = changesets.value
      if (csList.length) {
        const firstEl = idSidebarMap.current.get(csList[0].id.toString())
        const lastEl = idSidebarMap.current.get(csList.at(-1)!.id.toString())
        showScrollTop.value = firstEl
          ? firstEl.getBoundingClientRect().top < sidebarRect.top
          : false
        showScrollBottom.value = lastEl
          ? lastEl.getBoundingClientRect().bottom > sidebarRect.bottom
          : false
      } else {
        showScrollTop.value = false
        showScrollBottom.value = false
      }
    })
  }

  const updateLayersVisibilityNow = () => {
    const sidebarRect = parentSidebar.getBoundingClientRect()
    const csList = changesets.value

    // Calculate visibility for each changeset (backwards for early exit on hidden-above)
    let newHiddenBefore = 0
    let newHiddenAfter = 0
    let foundVisible = false
    const featureUpdates: [string, number, ScrollState["state"], number][] = []

    for (let i = csList.length - 1; i >= 0; i--) {
      const changeset = csList[i]
      const changesetId = changeset.id.toString()
      const element = idSidebarMap.current.get(changesetId)
      if (!element) continue

      const { state, distance } = getElementScrollState(
        element.getBoundingClientRect(),
        sidebarRect,
      )
      const hidden = state !== "visible" && distanceOpacity(distance) < 0.05

      if (!foundVisible && hidden) {
        newHiddenAfter++
      } else if (!hidden) {
        foundVisible = true
        featureUpdates.push([changesetId, changeset.bounds.length, state, distance])
      } else {
        // foundVisible && hidden → all remaining are hidden above
        newHiddenBefore = i + 1
        break
      }
    }

    // Update map layers if hidden ranges changed
    if (
      newHiddenBefore !== hiddenBefore.current ||
      newHiddenAfter !== hiddenAfter.current
    ) {
      hiddenBefore.current = newHiddenBefore
      hiddenAfter.current = newHiddenAfter
      updateLayers()
    }

    // Apply feature state updates
    for (const [id, numBounds, state, distance] of featureUpdates)
      updateFeatureState(id, numBounds, state, distance)

    updateScrollIndicators(sidebarRect)
  }

  // --- Fetch Logic ---

  const shouldReloadForBounds = (oldBounds: LngLatBounds, newBounds: LngLatBounds) => {
    const intersection = boundsIntersection(oldBounds, newBounds)
    const proportion =
      boundsSize(intersection) / Math.max(boundsSize(oldBounds), boundsSize(newBounds))
    return proportion <= RELOAD_PROPORTION_THRESHOLD
  }

  const determineFetchAction = (
    fetchBounds: LngLatBounds | null,
    fetchDate: string | undefined,
    fetchScope: "nearby" | "friends" | undefined,
    fetchDisplayName: string | undefined,
  ) => {
    const ctx = fetchedContext.current
    const ctxMatch =
      ctx.date === fetchDate &&
      ctx.scope === fetchScope &&
      ctx.displayName === fetchDisplayName

    if (ctxMatch && boundsEqual(ctx.bounds, fetchBounds)) {
      return noMoreChangesets.value ? "skip" : "paginate"
    }
    if (ctxMatch && ctx.bounds && fetchBounds) {
      return shouldReloadForBounds(ctx.bounds, fetchBounds) ? "reload" : "skip"
    }
    return "reload"
  }

  const buildFetchParams = (
    fetchBounds: LngLatBounds | null,
    fetchDate: string | undefined,
    fetchScope: "nearby" | "friends" | undefined,
    fetchDisplayName: string | undefined,
  ) => {
    const params: Record<string, string | undefined> = { date: fetchDate }
    if (fetchBounds) params.bbox = boundsToString(fetchBounds)
    params.scope = fetchScope
    params.display_name = fetchDisplayName
    return params
  }

  const fetchChangesets = async (options?: { fromMapMove?: boolean }) => {
    // Determine fetch bounds and date
    const fetchDate = date.value
    const fetchScope = scope.value
    const fetchDisplayName = displayName.value
    const isScoped = Boolean(fetchScope || fetchDisplayName)
    const fetchBounds = isScoped ? null : map.getBounds()
    if (options?.fromMapMove && !fetchBounds) return

    // Determine action based on context change
    const action = determineFetchAction(
      fetchBounds,
      fetchDate,
      fetchScope,
      fetchDisplayName,
    )
    if (action === "skip") return
    if (action === "reload") resetChangesets()

    // Build request params
    const params = buildFetchParams(
      fetchBounds,
      fetchDate,
      fetchScope,
      fetchDisplayName,
    )
    if (action === "paginate" && changesets.value.length) {
      params.before = changesets.value.at(-1)!.id.toString()
    }

    // Execute fetch
    fetchAbort.current?.abort()
    const thisAbort = new AbortController()
    fetchAbort.current = thisAbort
    loading.value = true

    try {
      const resp = await fetch(`/api/web/changeset/map${qsEncode(params)}`, {
        signal: thisAbort.signal,
        priority: "high",
      })
      assert(resp.ok, `${resp.status} ${resp.statusText}`)

      const buffer = await resp.arrayBuffer()
      thisAbort.signal.throwIfAborted()
      const newChangesets = fromBinary(
        RenderChangesetsDataSchema,
        new Uint8Array(buffer),
      ).changesets

      batch(() => {
        if (newChangesets.length) {
          for (const cs of newChangesets)
            idChangesetMap.current.set(cs.id.toString(), cs)

          const isFirstLoad = !changesets.value.length
          changesets.value = [...changesets.value, ...newChangesets]
          loading.value = false

          updateLayers(isFirstLoad)
          scheduleLayersVisibilityUpdateFn.current?.()
          scheduleCheckLoadMoreFn.current?.()
        } else {
          noMoreChangesets.value = true
        }

        fetchedContext.current = {
          bounds: fetchBounds,
          date: fetchDate,
          scope: fetchScope,
          displayName: fetchDisplayName,
        }
        loading.value = false
      })
    } catch (error) {
      if (error.name === "AbortError") return
      console.error("ChangesetsHistory: Failed to fetch", error)
      loading.value = false
    }
  }

  const checkLoadMore = () => {
    if (loading.value || noMoreChangesets.value || !loadMoreSentinel.current) return
    const sentinel = loadMoreSentinel.current
    const root = parentSidebar
    const sentinelRect = sentinel.getBoundingClientRect()
    const rootRect = root.getBoundingClientRect()
    // Check if sentinel is within buffer distance of visible area
    if (sentinelRect.top < rootRect.bottom + LOAD_MORE_SCROLL_BUFFER) {
      fetchChangesets()
    }
  }

  // --- Hover Logic ---

  const setHover = (
    id: string,
    numBounds: number,
    hover: boolean,
    scrollIntoView = false,
  ) => {
    const element = idSidebarMap.current.get(id)
    element?.classList.toggle("hover", hover)

    if (hover && scrollIntoView) {
      scrollElementIntoView(parentSidebar, element)
    }

    const firstFeatureId = idFirstFeatureIdMap.current.get(id)
    if (!firstFeatureId) return
    for (let i = firstFeatureId; i < firstFeatureId + numBounds * 2; i++) {
      map.setFeatureState({ source: LAYER_ID_BORDERS, id: i }, { hover })
      map.setFeatureState({ source: LAYER_ID, id: i }, { hover })
    }
  }

  const changesetIsWithinView = (changesetId: string) => {
    const cs = idChangesetMap.current.get(changesetId)
    if (!cs) return false
    const mapBounds = map.getBounds()
    return cs.bounds.some((b) => {
      const csBounds = new LngLatBounds([b.minLon, b.minLat, b.maxLon, b.maxLat])
      return boundsIntersect(mapBounds, csBounds)
    })
  }

  const scheduleSidebarFit = async (changesetId: string) => {
    sidebarHoverAbort.current?.abort()
    sidebarHoverAbort.current = new AbortController()

    try {
      await delay(FOCUS_HOVER_DELAY, { signal: sidebarHoverAbort.current.signal })
    } catch {
      return
    }

    if (
      !idFirstFeatureIdMap.current.has(changesetId) ||
      changesetIsWithinView(changesetId) ||
      !visibleChangesetsBounds.current
    )
      return

    map.fitBounds(boundsPadding(visibleChangesetsBounds.current, 0.3), {
      maxZoom: 16,
    })
  }

  const handleEntryMouseEnter = (changesetId: string) => {
    const changeset = idChangesetMap.current.get(changesetId)
    if (!changeset) return

    scheduleSidebarFit(changesetId)

    // Clear previous hover
    if (hoveredChangesetId.value && hoveredChangesetId.value !== changesetId) {
      const prev = idChangesetMap.current.get(hoveredChangesetId.value)
      if (prev) setHover(hoveredChangesetId.value, prev.bounds.length, false)
    }

    setHover(changesetId, changeset.bounds.length, true)
    hoveredChangesetId.value = changesetId
  }

  const handleEntryMouseLeave = (changesetId: string) => {
    sidebarHoverAbort.current?.abort()
    const changeset = idChangesetMap.current.get(changesetId)
    if (changeset) setHover(changesetId, changeset.bounds.length, false)
    if (hoveredChangesetId.value === changesetId) hoveredChangesetId.value = null
  }

  const registerEntry = (id: string, el: HTMLLIElement | null) => {
    if (el) idSidebarMap.current.set(id, el)
    else idSidebarMap.current.delete(id)
  }

  // --- Map Event Handlers ---

  const onMapMouseMove = async (e: MapLayerMouseEvent) => {
    const feature = pickSmallestBoundsFeature(e.features!)
    const id = feature.properties.id.toString()
    const numBounds = feature.properties.numBounds

    if (hoveredFeature.current) {
      if (hoveredFeature.current.id === feature.id) return
      setHover(
        hoveredFeature.current.properties.id.toString(),
        hoveredFeature.current.properties.numBounds,
        false,
      )
    } else {
      // Clear any sidebar hover when entering map hover
      if (hoveredChangesetId.value) {
        const prev = idChangesetMap.current.get(hoveredChangesetId.value)
        if (prev) setHover(hoveredChangesetId.value, prev.bounds.length, false)
        hoveredChangesetId.value = null
      }
      setMapHover(map, LAYER_ID)
    }

    scrollDelayAbort.current?.abort()
    scrollDelayAbort.current = new AbortController()
    hoveredFeature.current = feature
    setHover(id, numBounds, true)

    try {
      await delay(FOCUS_HOVER_DELAY, { signal: scrollDelayAbort.current.signal })
    } catch {
      return
    }
    setHover(id, numBounds, true, true)
  }

  const onMapMouseLeave = () => {
    if (!hoveredFeature.current) return
    scrollDelayAbort.current?.abort()
    setHover(
      hoveredFeature.current.properties.id.toString(),
      hoveredFeature.current.properties.numBounds,
      false,
    )
    hoveredFeature.current = null
    clearMapHover(map, LAYER_ID)
  }

  const onMapClick = (e: MapLayerMouseEvent) => {
    const id = pickSmallestBoundsFeature(e.features!).properties.id
    routerNavigate(ChangesetRoute, { id: BigInt(id) })
  }

  // Effect: Map lifecycle and event handlers
  useDisposeEffect((scope) => {
    scheduleLayersVisibilityUpdateFn.current = scope.frame(updateLayersVisibilityNow)
    scheduleCheckLoadMoreFn.current = scope.frame(checkLoadMore)

    scope.defer(() => {
      resetChangesets()
      scheduleLayersVisibilityUpdateFn.current = null
      scheduleCheckLoadMoreFn.current = null
    })

    scope.mapLayerLifecycle(map, LAYER_ID)
    scope.mapLayerLifecycle(map, LAYER_ID_BORDERS)
    const fillLayerId = getExtendedLayerId(LAYER_ID, "fill")
    scope.mapLayer(map, "mousemove", fillLayerId, onMapMouseMove)
    scope.mapLayer(map, "mouseleave", fillLayerId, onMapMouseLeave)
    scope.mapLayer(map, "click", fillLayerId, onMapClick)

    scope.map(map, "moveend", () => fetchChangesets({ fromMapMove: true }))
    scope.map(map, "zoomend", () => updateLayers())

    scope.dom(parentSidebar, "scroll", () =>
      scheduleLayersVisibilityUpdateFn.current?.(),
    )
  }, [])

  // Effect: Initial data fetch + refetch on context change.
  useSignalEffect(() => {
    date.value
    scope.value
    displayName.value
    fetchChangesets()
  })

  // Effect: Infinite scroll observer
  useEffect(() => {
    if (!loadMoreSentinel.current) return

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !loading.value && !noMoreChangesets.value) {
          fetchChangesets()
        }
      },
      { root: parentSidebar, rootMargin: `${LOAD_MORE_SCROLL_BUFFER}px` },
    )
    observer.observe(loadMoreSentinel.current)
    return () => observer.disconnect()
  }, [])

  return (
    <div class="sidebar-content">
      <div class="section">
        <SidebarHeader title={sidebarTitle.value.html} />

        {date.value && (
          <div class="alert alert-info py-2 px-3 mb-3 date-filter">
            <DateFilter date={date.value} />
          </div>
        )}

        <div class={`scroll-indicator top ${showScrollTop.value ? "visible" : ""}`}>
          <span class="indicator-text">{t("changesets_history.changesets_above")}</span>
        </div>

        <ul class="changesets-list social-list list-unstyled mb-0">
          {changesets.value.map((cs) => (
            <ChangesetEntry
              changeset={cs}
              key={cs.id}
              entryRef={registerEntry}
              onMouseEnter={handleEntryMouseEnter}
              onMouseLeave={handleEntryMouseLeave}
            />
          ))}
        </ul>
        <div ref={loadMoreSentinel} />

        {loading.value && <LoadingSpinner />}

        <div
          class={`scroll-indicator bottom ${showScrollBottom.value ? "visible" : ""}`}
        >
          <span class="indicator-text">{t("changesets_history.changesets_below")}</span>
        </div>
      </div>
    </div>
  )
}

const DateFilter = ({ date }: { date: string }) => {
  return (
    <>
      <span>{t("changeset.viewing_edits_from_date", { date })}</span>
      <a
        class="btn btn-sm btn-link btn-close"
        href={routerCtx.value.pathname}
        title={t("action.remove_filter")}
      >
        <span class="visually-hidden">{t("action.remove_filter")}</span>
      </a>
    </>
  )
}

const ChangesetEntry = ({
  changeset,
  entryRef,
  onMouseEnter,
  onMouseLeave,
}: {
  changeset: RenderChangesetsData_Changeset
  entryRef: (id: string, el: HTMLLIElement | null) => void
  onMouseEnter: (id: string) => void
  onMouseLeave: (id: string) => void
}) => {
  const changesetId = changeset.id.toString()
  const hasComments = changeset.numComments > 0n

  return (
    <li
      ref={(el) => entryRef(changesetId, el)}
      class="social-entry clickable"
      onMouseEnter={() => onMouseEnter(changesetId)}
      onMouseLeave={() => onMouseLeave(changesetId)}
    >
      <p class="header text-muted d-flex justify-content-between">
        <span>
          <span class="me-1">
            {changeset.user ? (
              <a href={`/user/${changeset.user.name}`}>
                <img
                  class="avatar"
                  src={changeset.user.avatarUrl}
                  alt={t("alt.profile_picture")}
                  loading="lazy"
                />
                {changeset.user.name}
              </a>
            ) : (
              t("browse.anonymous")
            )}
          </span>
          <span>
            {changeset.closed
              ? t("browse.closed").toLowerCase()
              : t("browse.created").toLowerCase()}{" "}
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
          <div class="comment">{changeset.comment || t("browse.no_comment")}</div>
          <div class={`num-comments${hasComments ? "" : " no-comments"}`}>
            {changeset.numComments.toString()}
            <i class={`bi ${hasComments ? "bi-chat-left-text" : "bi-chat-left"}`} />
          </div>
        </div>
        <ChangesetStats
          numCreate={changeset.numCreate}
          numModify={changeset.numModify}
          numDelete={changeset.numDelete}
        />
      </div>
    </li>
  )
}

export const ChangesetsHistoryRoute = defineRoute({
  id: "changesets-history",
  path: ["/history", "/history/:scope", "/user/:displayName/history"],
  params: {
    scope: routeParam.optional(routeParam.enum(["nearby", "friends"])),
    displayName: routeParam.optional(routeParam.segment()),
  },
  query: { date: queryParam.string() },
  Component: ChangesetsHistorySidebar,
})
