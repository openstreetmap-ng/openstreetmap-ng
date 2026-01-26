import { SidebarHeader, SidebarResourceBody } from "@index/_action-sidebar"
import { ElementRoute, getElementTypeLabel, getElementTypeSlug } from "@index/element"
import { defineRoute, routerNavigate } from "@index/router"
import { useSidebarSearchRpc } from "@index/search-rpc"
import { queryParam } from "@lib/codecs"
import { useDisposeEffect, useDisposeSignalEffect } from "@lib/dispose-scope"
import { mountMapAlert } from "@lib/map/alerts"
import { boundsIntersection, boundsPadding, boundsSize } from "@lib/map/bounds"
import { clearMapHover, setMapHover } from "@lib/map/hover"
import { loadMapImage } from "@lib/map/image"
import { type FocusLayerPaint, focusObjects } from "@lib/map/layers/focus-layer"
import {
  emptyFeatureCollection,
  type LayerId,
  layersConfig,
} from "@lib/map/layers/layers"
import { convertRenderElementsData } from "@lib/map/render-objects"
import { type LonLatZoom, lonLatZoomEquals } from "@lib/map/state"
import type { SearchData_ResultValid } from "@lib/proto/search_pb"
import type { ElementIcon, ElementType } from "@lib/proto/shared_pb"
import { scrollElementIntoView } from "@lib/scroll"
import { setPageTitle } from "@lib/title"
import type { OSMObject } from "@lib/types"
import {
  type ReadonlySignal,
  type Signal,
  signal,
  useSignal,
  useSignalEffect,
} from "@preact/signals"
import { memoize } from "@std/cache/memoize"
import type { Feature } from "geojson"
import { t } from "i18next"
import type { MapLayerMouseEvent } from "maplibre-gl"
import { type GeoJSONSource, LngLatBounds, type Map as MaplibreMap } from "maplibre-gl"
import type { MouseEventHandler, Ref } from "preact"
import { useRef } from "preact/hooks"

const LAYER_ID = "search" as LayerId
layersConfig.set(LAYER_ID, {
  specification: {
    type: "geojson",
    data: emptyFeatureCollection,
  },
  layerTypes: ["symbol"],
  layerOptions: {
    layout: {
      "icon-image": "marker-red",
      "icon-allow-overlap": true,
      "icon-size": 41 / 128,
      "icon-padding": 0,
      "icon-anchor": "bottom",
    },
    paint: {
      "icon-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 1, 0.8],
    },
  },
  priority: 150,
})

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

const SEARCH_ALERT_CHANGE_THRESHOLD = 0.9

export const searchFormQuery = signal("")

const SearchThisAreaAlert = ({
  visible,
  onClick,
}: {
  visible: ReadonlySignal<boolean>
  onClick: () => void
}) =>
  visible.value ? (
    <button
      class="btn btn-primary map-alert"
      type="button"
      onClick={onClick}
    >
      {t("search.search_this_area")}
    </button>
  ) : null

export const ElementResultEntry = ({
  result,
  hovered = false,
  entryRef,
  onFocus,
  onBlur,
}: {
  result: {
    type: ElementType
    id: bigint
    prefix: string
    displayName?: string
    icon?: ElementIcon
  }
  hovered?: boolean
  entryRef?: Ref<HTMLLIElement>
  onFocus?: MouseEventHandler<HTMLLIElement>
  onBlur?: MouseEventHandler<HTMLLIElement>
}) => {
  const idText = result.id.toString()
  const typeText = getElementTypeSlug(result.type)
  const displayNameText =
    result.displayName || `${getElementTypeLabel(result.type)} ${idText}`

  return (
    <li
      class={`social-entry clickable ${hovered ? "hover" : ""}`}
      ref={entryRef!}
      onMouseEnter={onFocus}
      onMouseLeave={onBlur}
    >
      <p class="header text-muted d-flex justify-content-between">
        <span>
          {result.icon && (
            <img
              class="icon me-1-5"
              loading="lazy"
              src={`/static/img/element/${result.icon.icon}`}
              title={result.icon.title}
              alt=""
            />
          )}
          {result.prefix}
        </span>
        <a
          class="stretched-link"
          href={`/${typeText}/${idText}`}
          aria-label={`${displayNameText} (${typeText}/${idText})`}
        >
          {typeText}/{idText}
        </a>
      </p>
      <p class="body">
        <bdi>{displayNameText}</bdi>
      </p>
    </li>
  )
}

const SearchResultsList = ({
  results,
  hoveredIndex,
  onHoverChange,
  entryRefs,
}: {
  results: SearchData_ResultValid[]
  hoveredIndex: ReadonlySignal<number | null>
  onHoverChange: (index: number | null) => void
  entryRefs: (HTMLLIElement | null)[]
}) =>
  results.length ? (
    <ul class="search-list social-list list-unstyled mb-0">
      {results.map((result, i) => (
        <ElementResultEntry
          key={`${result.type}:${result.id}`}
          result={result}
          hovered={hoveredIndex.value === i}
          entryRef={(el) => {
            entryRefs[i] = el
          }}
          onFocus={() => onHoverChange(i)}
          onBlur={() => onHoverChange(null)}
        />
      ))}
    </ul>
  ) : (
    <p>{t("results.we_did_not_find_any_results")}</p>
  )

const getFeatureIndex = (e: MapLayerMouseEvent) => {
  const featureId = e.features?.[0]?.id
  return typeof featureId === "number" ? featureId : null
}

const SearchSidebar = ({
  map,
  q,
  at,
  local,
}: {
  map: MaplibreMap
  q: Signal<string | undefined>
  at: Signal<LonLatZoom | undefined>
  local: Signal<boolean>
}) => {
  // Derived: sync page title with the current route state.
  setPageTitle(
    !q.value && at.value
      ? t("site.search.where_am_i")
      : q.value || t("site.search.search"),
  )
  const source = map.getSource<GeoJSONSource>(LAYER_ID)!

  const searchThisAreaVisible = useSignal(false)
  const onSearchThisAreaClick = () => {
    searchThisAreaVisible.value = false

    const query = q.peek()
    const { lng, lat } = map.getCenter()
    const nextAt = { lon: lng, lat, zoom: map.getZoom() }

    if (!query) {
      if (!at.peek()) return
      routerNavigate(SearchRoute, { at: nextAt })
      return
    }

    routerNavigate(SearchRoute, { q: query, at: nextAt, local: true })
  }

  const { resource, data } = useSidebarSearchRpc({ map, q, at, local })

  const hoveredIndex = useSignal<number | null>(null)
  const entryRefs = useRef<(HTMLLIElement | null)[]>([])
  const elementsByIndex = useRef<(() => OSMObject[])[]>([])

  // Effect: keep the global search input in sync with the active route.
  useSignalEffect(() => {
    searchFormQuery.value = q.value || ""
  })

  const setHoveredIndex = (nextIndex: number | null, scrollIntoView = false) => {
    const prevIndex = hoveredIndex.peek()
    if (prevIndex === nextIndex) return

    if (prevIndex !== null) {
      map.setFeatureState({ source: LAYER_ID, id: prevIndex }, { hover: false })
    }

    hoveredIndex.value = nextIndex

    if (nextIndex !== null) {
      map.setFeatureState({ source: LAYER_ID, id: nextIndex }, { hover: true })

      if (scrollIntoView) {
        const scrollSidebar = document
          .getElementById("ActionSidebar")!
          .closest(".sidebar")!
        const el = entryRefs.current[nextIndex]
        scrollElementIntoView(scrollSidebar, el)
      }

      const objects = elementsByIndex.current[nextIndex]?.()
      focusObjects(map, objects, focusPaint, null, false)
    } else {
      focusObjects(map)
    }
  }

  const clearResultsState = () => {
    entryRefs.current.length = 0
    elementsByIndex.current = []
    searchThisAreaVisible.value = false

    if (hoveredIndex.peek() !== null) setHoveredIndex(null)
    else focusObjects(map)
    clearMapHover(map, LAYER_ID)
    source.setData(emptyFeatureCollection)
  }

  // Effect: map layer lifecycle + hover/click handlers (stable; reads latest results via peek()).
  useDisposeEffect((scope) => {
    const searchForm = document.getElementById("SearchForm")!
    searchForm.classList.add("sticky-top")
    scope.defer(() => searchForm.classList.remove("sticky-top"))

    scope.defer(
      mountMapAlert(
        <SearchThisAreaAlert
          visible={searchThisAreaVisible}
          onClick={onSearchThisAreaClick}
        />,
      ),
    )

    loadMapImage(map, "marker-red")
    scope.mapLayerLifecycle(map, LAYER_ID)
    scope.defer(clearResultsState)

    scope.mapLayer(map, "click", LAYER_ID, (e) => {
      const featureIndex = getFeatureIndex(e)
      if (featureIndex === null) return
      const result = data.peek()?.results[featureIndex]
      if (!result) return
      const typeSlug = getElementTypeSlug(result.type)
      routerNavigate(ElementRoute, { type: typeSlug, id: result.id })
    })

    scope.mapLayer(map, "mousemove", LAYER_ID, (e) => {
      const featureIndex = getFeatureIndex(e)
      if (featureIndex === null) return
      setMapHover(map, LAYER_ID)
      setHoveredIndex(featureIndex, true)
    })
    scope.mapLayer(map, "mouseleave", LAYER_ID, () => {
      clearMapHover(map, LAYER_ID)
      setHoveredIndex(null)
    })
  }, [])

  // Effect: keep the map view synced to the `at` query param.
  useSignalEffect(() => {
    const view = at.value
    if (!view) return

    const { lng, lat } = map.getCenter()
    const currentView = { lon: lng, lat, zoom: map.getZoom() }
    if (lonLatZoomEquals(currentView, view)) return

    map.jumpTo({ center: [view.lon, view.lat], zoom: view.zoom })
  })

  // Effect: when the route has no active request (no `q` and no `at`), clear any stale UI state.
  useSignalEffect(() => {
    if (q.value || at.value) return
    clearResultsState()
  })

  // Effect: on each successful load, update markers + focus cache + auto-fit + "search this area" trigger.
  useDisposeSignalEffect((scope) => {
    const d = data.value
    if (!d) return
    searchThisAreaVisible.value = false

    // Clear any existing hover state before replacing data.
    clearMapHover(map, LAYER_ID)
    setHoveredIndex(null)

    entryRefs.current.length = d.results.length
    elementsByIndex.current = d.results.map((r) =>
      memoize(() => convertRenderElementsData(r.render)),
    )

    const features: Feature[] = d.results.map((result, i) => ({
      type: "Feature",
      id: i,
      properties: {},
      geometry: {
        type: "Point",
        coordinates: [result.location.lon, result.location.lat],
      },
    }))
    source.setData({ type: "FeatureCollection", features })

    const shouldAutoFit =
      Boolean(q.peek()) && (Boolean(d.bounds) || d.results.length > 0)

    let initialBounds = shouldAutoFit ? null : map.getBounds()

    const moveEndScope = scope.child()
    moveEndScope.map(map, "moveend", () => {
      if (!initialBounds) {
        initialBounds = map.getBounds()
        console.debug("Search: Initial bounds set", initialBounds)
        return
      }

      const mapBounds = map.getBounds()
      const intersectionBounds = boundsIntersection(initialBounds, mapBounds)
      const intersectionBoundsSize = boundsSize(intersectionBounds)
      const proportion = Math.min(
        intersectionBoundsSize / boundsSize(mapBounds),
        intersectionBoundsSize / boundsSize(initialBounds),
      )
      if (proportion > SEARCH_ALERT_CHANGE_THRESHOLD) return

      searchThisAreaVisible.value = true
      moveEndScope.dispose()
    })

    if (shouldAutoFit) {
      const b = d.bounds
      if (b) {
        const boundsPadded = boundsPadding(
          new LngLatBounds([b.minLon, b.minLat, b.maxLon, b.maxLat]),
          0.05,
        )
        map.fitBounds(boundsPadded, { maxZoom: 14 })
      } else if (d.results.length) {
        const [first, ...rest] = d.results
        const markersBounds = rest.reduce(
          (bounds, r) => bounds.extend([r.location.lon, r.location.lat]),
          new LngLatBounds([
            first.location.lon,
            first.location.lat,
            first.location.lon,
            first.location.lat,
          ]),
        )
        const boundsPadded = boundsPadding(markersBounds, 0.15)
        map.fitBounds(boundsPadded, { maxZoom: 14 })
      }
    }
  })

  return (
    <div class="sidebar-content">
      <div class="section">
        <SidebarHeader title={t("site.sidebar.search_results")} />
        <SidebarResourceBody resource={resource}>
          {(d) => (
            <SearchResultsList
              results={d.results}
              hoveredIndex={hoveredIndex}
              onHoverChange={setHoveredIndex}
              entryRefs={entryRefs.current}
            />
          )}
        </SidebarResourceBody>
      </div>
    </div>
  )
}

export const SearchRoute = defineRoute({
  id: "search",
  path: "/search",
  aliases: { query: { query: "q" } },
  query: {
    q: queryParam.string(),
    at: queryParam.lonLatZoom(),
    local: queryParam.flag(),
  },
  Component: SearchSidebar,
})
