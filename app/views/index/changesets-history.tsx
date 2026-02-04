import { LoadingSpinner, SidebarHeader } from "@index/_action-sidebar"
import { ChangesetRoute, ChangesetStats } from "@index/changeset"
import { defineRoute, routerCtx, routerNavigate } from "@index/router"
import { queryParam, routeParam } from "@lib/codecs"
import { darkenColor } from "@lib/color"
import { Time } from "@lib/datetime-inputs"
import { type Scheduled, useDisposeEffect } from "@lib/dispose-scope"
import { tRich } from "@lib/i18n"
import { createKeyedAbort, type KeyedAbortToken } from "@lib/keyed-abort"
import {
  boundsEqual,
  boundsIntersect,
  boundsIntersection,
  boundsPadding,
  boundsSize,
  boundsToProto,
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
} from "@lib/map/layers/layers"
import { renderObjects } from "@lib/map/render-objects"
import {
  type GetMapChangesetsResponse_ChangesetValid as Changeset,
  ChangesetService,
  GetMapChangesetsRequest_Scope,
} from "@lib/proto/changeset_pb"
import { rpcClient } from "@lib/rpc"
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
import type { ComponentChildren, RefObject } from "preact"
import { useRef } from "preact/hooks"

// Constants

const FADE_SPEED = 0.2
const THICKNESS_SPEED = FADE_SPEED * 0.6
const LINE_WIDTH = 3
const FOCUS_HOVER_DELAY = SECOND
const LOAD_MORE_SCROLL_BUFFER = 1000
const RELOAD_PROPORTION_THRESHOLD = 0.9

// Map layers

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

type FetchContext = Readonly<{
  bounds: LngLatBounds | null
  date: string | undefined
  scope: "nearby" | "friends" | undefined
  displayName: string | undefined
}>

type ActiveFetch = Readonly<{ token: KeyedAbortToken; ctx: FetchContext }>

const EMPTY_CONTEXT: FetchContext = {
  bounds: null,
  date: undefined,
  scope: undefined,
  displayName: undefined,
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

const ChangesetsHistorySidebar = ({
  map,
  sidebarRef,
  date,
  scope,
  displayName,
}: {
  map: MaplibreMap
  sidebarRef: RefObject<HTMLElement>
  date: ReadonlySignal<string | undefined>
  scope: ReadonlySignal<"nearby" | "friends" | undefined>
  displayName: ReadonlySignal<string | undefined>
}) => {
  const rootRef = useRef<HTMLDivElement>(null)
  const getEntryEl = (changesetId: string) =>
    rootRef.current?.querySelector(`li[data-changeset-id="${changesetId}"]`)

  const changesets = useSignal<Changeset[]>([])
  const noMoreChangesets = useSignal(false)
  const showScrollTop = useSignal(false)
  const showScrollBottom = useSignal(false)

  const fetchAbort = useRef(createKeyedAbort()).current

  const scrollIndicatorsEnabled = useComputed(
    () => !fetchAbort.pending.value && changesets.value.length > 0,
  )

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

  const loadMoreSentinel = useRef<HTMLDivElement>(null)

  type HoverState =
    | Readonly<{ source: "sidebar"; id: string; numBounds: number }>
    | Readonly<{ source: "map"; id: string; numBounds: number; featureId: number }>

  const hoverState = useRef<HoverState | null>(null)

  const idFirstFeatureIdMap = useRef(new Map<string, number>())

  const activeFetch = useRef<ActiveFetch | null>(null)
  const fetchedContext = useRef<FetchContext>(EMPTY_CONTEXT)

  const layerState = useRef<{
    hiddenBefore: number
    hiddenAfter: number
    visibleBounds: LngLatBounds | null
  }>({ hiddenBefore: 0, hiddenAfter: 0, visibleBounds: null })

  const scheduleLayersVisibilityUpdateFn = useRef<Scheduled<() => void> | null>(null)
  const scheduleSidebarFitFn = useRef<Scheduled<(cs: Changeset) => void> | null>(null)
  const scheduleMapScrollFn = useRef<Scheduled<(id: string) => void> | null>(null)

  const clearDerivedState = () => {
    setHoverState(null)

    showScrollTop.value = false
    showScrollBottom.value = false

    idFirstFeatureIdMap.current.clear()
    layerState.current.visibleBounds = null
    layerState.current.hiddenBefore = 0
    layerState.current.hiddenAfter = 0
  }

  const resetChangesets = () => {
    fetchAbort.abort()
    activeFetch.current = null
    fetchedContext.current = EMPTY_CONTEXT

    batch(() => {
      changesets.value = []
      noMoreChangesets.value = false
      clearDerivedState()
    })

    const source = map.getSource<GeoJSONSource>(LAYER_ID)
    const sourceBorders = map.getSource<GeoJSONSource>(LAYER_ID_BORDERS)
    source?.setData(emptyFeatureCollection)
    sourceBorders?.setData(emptyFeatureCollection)
  }

  const setFeatureStateRange = (
    firstFeatureId: number,
    numBounds: number,
    state: Record<string, unknown>,
  ) => {
    if (!map.getSource(LAYER_ID) || !map.getSource(LAYER_ID_BORDERS)) return

    for (let i = firstFeatureId; i < firstFeatureId + numBounds * 2; i++) {
      map.setFeatureState({ source: LAYER_ID_BORDERS, id: i }, state)
      map.setFeatureState({ source: LAYER_ID, id: i }, state)
    }
  }

  const setEntryHoverClass = (id: string, hover: boolean) => {
    const el = getEntryEl(id)
    el?.classList.toggle("hover", hover)
  }

  const setHoverState = (next: HoverState | null) => {
    const prev = hoverState.current
    if (prev?.source === "sidebar" && next?.source !== "sidebar")
      scheduleSidebarFitFn.current?.cancel()

    if (prev?.source === "map" && next?.source !== "map") {
      scheduleMapScrollFn.current?.cancel()
      clearMapHover(map, LAYER_ID)
    }

    if (next?.source === "map" && prev?.source !== "map") setMapHover(map, LAYER_ID)

    if (prev && (!next || prev.id !== next.id)) {
      setEntryHoverClass(prev.id, false)
      setHover(prev.id, prev.numBounds, false)
    }
    if (next && (!prev || prev.id !== next.id)) {
      setEntryHoverClass(next.id, true)
      setHover(next.id, next.numBounds, true)
    }

    hoverState.current = next
  }

  const updateFeatureState = (
    changesetId: string,
    numBounds: number,
    state: "above" | "visible" | "below",
    distance: number,
  ) => {
    const firstFeatureId = idFirstFeatureIdMap.current.get(changesetId)
    if (firstFeatureId === undefined) return

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

    setFeatureStateRange(firstFeatureId, numBounds, featureState)
  }

  const rebuildLayers = (opts?: { fit?: boolean }) => {
    const csList = changesets.value
    let featureIdCounter = 1
    for (let i = 0; i < layerState.current.hiddenBefore; i++)
      featureIdCounter += csList[i].bounds.length * 2

    idFirstFeatureIdMap.current.clear()
    const changesetsMinimumSize: OSMChangeset[] = []
    let aggregatedBounds: Bounds | undefined

    let firstFeatureId = featureIdCounter
    const visibleChangesets = csList.slice(
      layerState.current.hiddenBefore,
      csList.length - layerState.current.hiddenAfter,
    )

    for (const cs of visibleChangesets) {
      const csId = cs.id.toString()
      idFirstFeatureIdMap.current.set(csId, firstFeatureId)
      firstFeatureId += cs.bounds.length * 2

      const resizedBounds: Bounds[] = []
      for (const { minLon, minLat, maxLon, maxLat } of cs.bounds) {
        const resized = makeBoundsMinimumSize(map, [minLon, minLat, maxLon, maxLat])
        aggregatedBounds = boundsUnion(aggregatedBounds, resized)
        resizedBounds.push(resized)
      }

      changesetsMinimumSize.push({
        type: "changeset",
        id: cs.id,
        bounds: resizedBounds,
      })
    }

    const bounds = aggregatedBounds ? new LngLatBounds(aggregatedBounds) : null
    layerState.current.visibleBounds = bounds

    const data = renderObjects(changesetsMinimumSize, { featureIdCounter })
    const source = map.getSource<GeoJSONSource>(LAYER_ID)
    const sourceBorders = map.getSource<GeoJSONSource>(LAYER_ID_BORDERS)
    if (!(source && sourceBorders)) return
    source.setData(data)
    sourceBorders.setData(data)

    const h = hoverState.current
    if (h) setHover(h.id, h.numBounds, true)

    if (opts?.fit && bounds) {
      map.fitBounds(boundsPadding(bounds, 0.3), { maxZoom: 16, animate: false })
    }
  }

  const maybeLoadMore = (sidebarRect: DOMRect) => {
    if (
      fetchAbort.pending.peek() ||
      noMoreChangesets.peek() ||
      !loadMoreSentinel.current
    )
      return

    const sentinelRect = loadMoreSentinel.current.getBoundingClientRect()
    if (sentinelRect.top < sidebarRect.bottom + LOAD_MORE_SCROLL_BUFFER) {
      void fetchChangesets()
    }
  }

  const updateLayersVisibilityNow = () => {
    const parentSidebar = sidebarRef.current!
    const sidebarRect = parentSidebar.getBoundingClientRect()
    const csList = changesets.value
    const hoveredId = hoverState.current?.id

    // Calculate visibility for each changeset (backwards for early exit on hidden-above)
    let newHiddenBefore = 0
    let newHiddenAfter = 0
    let foundVisible = false
    let hasAbove = false
    let hasBelow = false
    const featureUpdates: [string, number, ScrollState["state"], number][] = []

    for (let i = csList.length - 1; i >= 0; i--) {
      const changeset = csList[i]
      const changesetId = changeset.id.toString()
      const element = getEntryEl(changesetId)
      if (!element) continue

      const { state, distance } = getElementScrollState(
        element.getBoundingClientRect(),
        sidebarRect,
      )
      const hidden = state !== "visible" && distanceOpacity(distance) < 0.05
      if (state === "above") hasAbove = true
      else if (state === "below") hasBelow = true

      if (!foundVisible && hidden) {
        newHiddenAfter++
        hasBelow = true
      } else if (!hidden) {
        foundVisible = true
        featureUpdates.push([changesetId, changeset.bounds.length, state, distance])
      } else {
        // foundVisible && hidden → all remaining are hidden above
        newHiddenBefore = i + 1
        hasAbove = true
        break
      }
    }

    // Update map layers if hidden ranges changed
    const prev = layerState.current
    if (newHiddenBefore !== prev.hiddenBefore || newHiddenAfter !== prev.hiddenAfter) {
      prev.hiddenBefore = newHiddenBefore
      prev.hiddenAfter = newHiddenAfter
      rebuildLayers()
    }

    // Apply feature state updates
    for (const [id, numBounds, state, distance] of featureUpdates)
      updateFeatureState(id, numBounds, state, distance)

    if (hoveredId) setEntryHoverClass(hoveredId, true)

    batch(() => {
      showScrollTop.value = hasAbove
      showScrollBottom.value = hasBelow
    })

    maybeLoadMore(sidebarRect)
  }

  // Fetch

  const shouldReloadForBounds = (oldBounds: LngLatBounds, newBounds: LngLatBounds) => {
    const intersection = boundsIntersection(oldBounds, newBounds)
    const proportion =
      boundsSize(intersection) / Math.max(boundsSize(oldBounds), boundsSize(newBounds))
    return proportion <= RELOAD_PROPORTION_THRESHOLD
  }

  type FetchDecision =
    | Readonly<{ action: "skip" }>
    | Readonly<{ action: "reload"; requestContext: FetchContext }>
    | Readonly<{ action: "paginate"; requestContext: FetchContext }>

  const determineFetchDecision = (next: FetchContext): FetchDecision => {
    const isPending = fetchAbort.pending.peek()
    const ctx = (isPending ? activeFetch.current?.ctx : null) ?? fetchedContext.current
    const ctxMatch =
      ctx.date === next.date &&
      ctx.scope === next.scope &&
      ctx.displayName === next.displayName

    if (!ctxMatch) return { action: "reload", requestContext: next }

    if (boundsEqual(ctx.bounds, next.bounds)) {
      // Prevent duplicate triggers while a request is in-flight.
      if (isPending || noMoreChangesets.peek()) return { action: "skip" }
      return { action: "paginate", requestContext: ctx }
    }
    if (ctx.bounds && next.bounds) {
      if (shouldReloadForBounds(ctx.bounds, next.bounds))
        return { action: "reload", requestContext: next }
      if (isPending || noMoreChangesets.peek()) return { action: "skip" }
      // Treat small pans as "same query" and continue paginating the last fetched bounds.
      return { action: "paginate", requestContext: ctx }
    }
    return { action: "reload", requestContext: next }
  }

  const fetchChangesets = async (options?: { fromMapMove?: boolean }) => {
    const fetchDate = date.value
    const fetchScope = scope.value
    const fetchDisplayName = displayName.value
    const isScoped = Boolean(fetchScope || fetchDisplayName)
    const fetchBounds = isScoped ? null : map.getBounds()
    if (options?.fromMapMove && !fetchBounds) return

    const nextContext: FetchContext = {
      bounds: fetchBounds,
      date: fetchDate,
      scope: fetchScope,
      displayName: fetchDisplayName,
    }

    const decision = determineFetchDecision(nextContext)
    if (decision.action === "skip") return

    if (decision.action === "reload") resetChangesets()

    // Map movements should never trigger pagination; pagination is driven by the sentinel.
    if (options?.fromMapMove && decision.action === "paginate") return

    const requestContext = decision.requestContext

    const beforeId =
      decision.action === "paginate" ? (changesets.peek().at(-1)?.id ?? null) : null

    const bbox = requestContext.bounds
      ? boundsToProto(requestContext.bounds)
      : undefined
    const bboxKey = requestContext.bounds ? boundsToString(requestContext.bounds) : ""
    const fetchKey = [
      bboxKey,
      requestContext.date ?? "",
      requestContext.scope ?? "",
      requestContext.displayName ?? "",
      beforeId?.toString() ?? "",
    ].join(":")

    const token = fetchAbort.start(fetchKey)
    if (!token) return

    const shouldFit =
      decision.action === "reload" &&
      routerCtx.peek().reason === "navigation" &&
      Boolean(nextContext.scope || nextContext.displayName) &&
      changesets.peek().length === 0

    activeFetch.current = {
      token,
      ctx: requestContext,
    }

    try {
      const resp = await rpcClient(ChangesetService).getMapChangesets(
        {
          bbox,
          scope: requestContext.scope
            ? GetMapChangesetsRequest_Scope[requestContext.scope]
            : undefined,
          displayName: requestContext.displayName,
          date: requestContext.date,
          before: beforeId ?? undefined,
        },
        { signal: token.signal },
      )
      token.signal.throwIfAborted()
      const newChangesets = resp.changesets

      batch(() => {
        fetchedContext.current = requestContext

        if (!newChangesets.length) {
          if (decision.action === "reload") {
            changesets.value = []
            clearDerivedState()
            rebuildLayers()
          }
          noMoreChangesets.value = true
          return
        }

        if (decision.action === "reload") {
          noMoreChangesets.value = false
          clearDerivedState()
          changesets.value = newChangesets
        } else {
          changesets.value = [...changesets.value, ...newChangesets]
        }

        rebuildLayers({ fit: shouldFit })
        scheduleLayersVisibilityUpdateFn.current?.()
      })
    } catch (error) {
      if (error.name === "AbortError") return
      console.error("ChangesetsHistory: Failed to fetch", error)
    } finally {
      token.done()
      if (activeFetch.current?.token === token) activeFetch.current = null
    }
  }

  const scrollChangesetIntoView = (id: string) => {
    const parentSidebar = sidebarRef.current!
    const element = getEntryEl(id)
    scrollElementIntoView(parentSidebar, element)
  }

  const setHover = (id: string, numBounds: number, hover: boolean) => {
    const firstFeatureId = idFirstFeatureIdMap.current.get(id)
    if (firstFeatureId === undefined) return
    setFeatureStateRange(firstFeatureId, numBounds, { hover })
  }

  const changesetIsWithinView = (changeset: Changeset) => {
    const mapBounds = map.getBounds()
    return changeset.bounds.some((b) => {
      const csBounds = new LngLatBounds([b.minLon, b.minLat, b.maxLon, b.maxLat])
      return boundsIntersect(mapBounds, csBounds)
    })
  }

  const handleEntryMouseEnter = (changeset: Changeset) => {
    const changesetId = changeset.id.toString()
    setHoverState({
      source: "sidebar",
      id: changesetId,
      numBounds: changeset.bounds.length,
    })
    scheduleSidebarFitFn.current?.(changeset)
  }

  const handleEntryMouseLeave = (changeset: Changeset) => {
    const changesetId = changeset.id.toString()
    const h = hoverState.current
    if (h?.source === "sidebar" && h.id === changesetId) setHoverState(null)
  }

  const onMapMouseMove = (e: MapLayerMouseEvent) => {
    const feature = pickSmallestBoundsFeature(e.features!)
    const id = feature.properties.id.toString()
    const numBounds = Number(feature.properties.numBounds)
    const featureId = feature.id as number

    const h = hoverState.current
    if (h && h.source === "map" && h.featureId === featureId) return

    setHoverState({ source: "map", id, numBounds, featureId })

    scheduleMapScrollFn.current?.(id)
  }

  const onMapMouseLeave = () => {
    if (hoverState.current?.source === "map") setHoverState(null)
  }

  const onMapClick = (e: MapLayerMouseEvent) => {
    const id = pickSmallestBoundsFeature(e.features!).properties.id
    routerNavigate(ChangesetRoute, { id: BigInt(id) })
  }

  // Effect: map + DOM lifecycle
  useDisposeEffect((scope) => {
    const parentSidebar = sidebarRef.current!

    scheduleLayersVisibilityUpdateFn.current = scope.frame(updateLayersVisibilityNow)
    scheduleSidebarFitFn.current = scope.debounce(
      FOCUS_HOVER_DELAY,
      (cs: Changeset) => {
        const changesetId = cs.id.toString()
        const h = hoverState.current
        if (h?.source !== "sidebar" || h.id !== changesetId) return
        if (
          !idFirstFeatureIdMap.current.has(changesetId) ||
          changesetIsWithinView(cs) ||
          !layerState.current.visibleBounds
        )
          return

        map.fitBounds(boundsPadding(layerState.current.visibleBounds, 0.3), {
          maxZoom: 16,
        })
      },
    )
    scheduleMapScrollFn.current = scope.debounce(FOCUS_HOVER_DELAY, (id) => {
      const h = hoverState.current
      if (h?.source !== "map" || h.id !== id) return
      scrollChangesetIntoView(id)
    })

    scope.defer(() => {
      resetChangesets()
      scheduleLayersVisibilityUpdateFn.current = null
      scheduleSidebarFitFn.current = null
      scheduleMapScrollFn.current = null
    })

    scope.mapLayerLifecycle(map, LAYER_ID)
    scope.mapLayerLifecycle(map, LAYER_ID_BORDERS)
    const fillLayerId = getExtendedLayerId(LAYER_ID, "fill")
    scope.mapLayer(map, "mousemove", fillLayerId, onMapMouseMove)
    scope.mapLayer(map, "mouseleave", fillLayerId, onMapMouseLeave)
    scope.mapLayer(map, "click", fillLayerId, onMapClick)

    scope.map(map, "moveend", () => void fetchChangesets({ fromMapMove: true }))
    scope.map(map, "zoomend", () => rebuildLayers())

    scope.dom(parentSidebar, "scroll", () => {
      scheduleLayersVisibilityUpdateFn.current?.()
    })
    scope.dom(window, "resize", () => {
      scheduleLayersVisibilityUpdateFn.current?.()
    })
  }, [])

  // Effect: fetch (and refetch) changesets
  useSignalEffect(() => {
    void fetchChangesets()
  })

  return (
    <div
      class="sidebar-content"
      ref={rootRef}
    >
      <div class="section">
        <SidebarHeader title={sidebarTitle.value.html} />

        {date.value && (
          <div class="alert alert-info py-2 px-3 mb-3 date-filter">
            <DateFilter date={date.value} />
          </div>
        )}

        <ScrollIndicator
          position="top"
          enabled={scrollIndicatorsEnabled}
          visible={showScrollTop}
        >
          {t("changesets_history.changesets_above")}
        </ScrollIndicator>

        <ul class="changesets-list social-list list-unstyled mb-0">
          {changesets.value.map((cs) => (
            <ChangesetEntry
              key={cs.id}
              changeset={cs}
              onMouseEnter={handleEntryMouseEnter}
              onMouseLeave={handleEntryMouseLeave}
            />
          ))}
        </ul>
        <div ref={loadMoreSentinel} />

        {fetchAbort.pending.value && <LoadingSpinner />}

        <ScrollIndicator
          position="bottom"
          enabled={scrollIndicatorsEnabled}
          visible={showScrollBottom}
        >
          {t("changesets_history.changesets_below")}
        </ScrollIndicator>
      </div>
    </div>
  )
}

const DateFilter = ({ date }: { date: string }) => (
  <>
    <span>{t("changeset.viewing_edits_from_date", { date })}</span>
    <a
      class="btn btn-sm btn-link btn-close"
      href={routerCtx.value.pathname}
      title={t("action.remove_filter")}
      aria-label={t("action.remove_filter")}
    />
  </>
)

const ScrollIndicator = ({
  position,
  enabled,
  visible,
  children,
}: {
  position: "top" | "bottom"
  enabled: ReadonlySignal<boolean>
  visible: ReadonlySignal<boolean>
  children: ComponentChildren
}) => (
  <div
    class={`scroll-indicator ${position} ${enabled.value && visible.value ? "visible" : ""} ${
      enabled.value ? "" : "no-transition"
    }`}
  >
    <span class="indicator-text">{children}</span>
  </div>
)

const ChangesetEntry = ({
  changeset,
  onMouseEnter,
  onMouseLeave,
}: {
  changeset: Changeset
  onMouseEnter: (changeset: Changeset) => void
  onMouseLeave: (changeset: Changeset) => void
}) => {
  const changesetId = changeset.id.toString()
  const hasComments = changeset.numComments > 0n

  return (
    <li
      data-changeset-id={changesetId}
      class="social-entry clickable"
      onMouseEnter={() => onMouseEnter(changeset)}
      onMouseLeave={() => onMouseLeave(changeset)}
    >
      <p class="header text-muted d-flex justify-content-between">
        <span>
          <span class="me-1">
            {changeset.user ? (
              <a href={`/user/${changeset.user.displayName}`}>
                <img
                  class="avatar"
                  src={changeset.user.avatarUrl}
                  alt={t("alt.profile_picture")}
                  loading="lazy"
                />
                {changeset.user.displayName}
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
              unix={changeset.statusChangedAt}
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
          <div class={`num-comments ${hasComments ? "" : "no-comments"}`}>
            {changeset.numComments}
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
