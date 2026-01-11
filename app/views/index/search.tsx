import {
  getActionSidebar,
  SidebarHeader,
  SidebarResourceBody,
  switchActionSidebar,
  useSidebarFetch,
} from "@index/_action-sidebar"
import { getElementTypeLabel, getElementTypeSlug } from "@index/element"
import { routerNavigateStrict } from "@index/router"
import { searchFormQuery } from "@index/search-form"
import { zoomPrecision } from "@lib/coords"
import { mountMapAlert } from "@lib/map/alerts"
import {
  boundsIntersection,
  boundsPadding,
  boundsSize,
  boundsToString,
} from "@lib/map/bounds"
import { clearMapHover, setMapHover } from "@lib/map/hover"
import { loadMapImage } from "@lib/map/image"
import { type FocusLayerPaint, focusObjects } from "@lib/map/layers/focus-layer"
import {
  addMapLayer,
  emptyFeatureCollection,
  type LayerId,
  layersConfig,
  removeMapLayer,
} from "@lib/map/layers/layers"
import { convertRenderElementsData } from "@lib/map/render-objects"
import { encodeMapState, type LonLatZoom, parseLonLatZoom } from "@lib/map/state"
import type { ElementIcon, ElementType, SearchData_Result } from "@lib/proto/shared_pb"
import { SearchDataSchema } from "@lib/proto/shared_pb"
import { qsEncode, qsParse } from "@lib/qs"
import { scrollElementIntoView } from "@lib/scroll"
import { setPageTitle } from "@lib/title"
import type { OSMObject } from "@lib/types"
import {
  type ReadonlySignal,
  type Signal,
  signal,
  useComputed,
  useSignal,
  useSignalEffect,
} from "@preact/signals"
import { assertExists } from "@std/assert"
import { memoize } from "@std/cache/memoize"
import type { Feature } from "geojson"
import { t } from "i18next"
import type { MapLayerMouseEvent } from "maplibre-gl"
import { type GeoJSONSource, LngLatBounds, type Map as MaplibreMap } from "maplibre-gl"
import { type MouseEventHandler, type Ref, render } from "preact"
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

type SearchRoute =
  | null
  | { tag: "query"; query: string; localOnly: boolean; at: LonLatZoom | null }
  | { tag: "where-is-this"; at: LonLatZoom }

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
  results: SearchData_Result[]
  hoveredIndex: ReadonlySignal<number | null>
  onHoverChange: (index: number | null) => void
  entryRefs: (HTMLLIElement | null)[]
}) =>
  results.length ? (
    <ul class="search-list social-list list-unstyled mb-0">
      {results.map((result, i) => (
        <ElementResultEntry
          key={`${result.type}:${result.id.toString()}`}
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

const computeSearchURL = (map: MaplibreMap, route: SearchRoute) => {
  if (!route) return null

  if (route.tag === "where-is-this") {
    const { lon, lat, zoom } = route.at
    const precision = zoomPrecision(zoom)
    return `/api/web/search/where-is-this${qsEncode({
      lon: lon.toFixed(precision),
      lat: lat.toFixed(precision),
      zoom: Math.round(zoom).toString(),
    })}`
  }

  if (!route.query) return null

  return `/api/web/search/results${qsEncode({
    q: route.query,
    bbox: boundsToString(boundsPadding(map.getBounds(), -0.01)),
    local_only: route.localOnly ? "1" : undefined,
  })}`
}

const SearchSidebar = ({
  map,
  source,
  sidebar,
  searchForm,
  route,
  searchThisAreaVisible,
}: {
  map: MaplibreMap
  source: GeoJSONSource
  sidebar: HTMLElement
  searchForm: HTMLElement
  route: Signal<SearchRoute>
  searchThisAreaVisible: Signal<boolean>
}) => {
  const scrollSidebar = sidebar.closest(".sidebar")!

  const active = useComputed(() => Boolean(route.value))
  const url = useComputed(() => computeSearchURL(map, route.value))
  const { resource, data } = useSidebarFetch(url, SearchDataSchema)

  const hoveredIndex = useSignal<number | null>(null)
  const entryRefs = useRef<(HTMLLIElement | null)[]>([])
  const elementsByIndex = useRef<(() => OSMObject[])[]>([])

  // Effect: sidebar lifecycle (visibility/title) + sticky search form.
  useSignalEffect(() => {
    if (!active.value) return
    switchActionSidebar(map, sidebar)
    searchForm.classList.add("sticky-top")

    return () => {
      searchForm.classList.remove("sticky-top")
    }
  })

  // Effect: page title.
  useSignalEffect(() => {
    const r = route.value
    if (!r) return

    setPageTitle(
      r.tag === "where-is-this"
        ? t("site.search.where_am_i")
        : r.query || t("site.search.search"),
    )
  })

  // Effect: keep search form query in sync with the active route.
  useSignalEffect(() => {
    const r = route.value
    if (!r) return
    searchFormQuery.value = r.tag === "where-is-this" ? "" : r.query
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
        const el = entryRefs.current[nextIndex]
        if (el) scrollElementIntoView(scrollSidebar, el)
      }

      const objects = elementsByIndex.current[nextIndex]?.()
      focusObjects(map, objects, focusPaint, null, false)
    } else {
      focusObjects(map)
    }
  }

  // Effect: map layer lifecycle + map hover handlers.
  useSignalEffect(() => {
    if (!active.value) return

    loadMapImage(map, "marker-red")
    addMapLayer(map, LAYER_ID)

    const getFeatureIndex = (e: MapLayerMouseEvent) => {
      const featureId = e.features?.[0]?.id
      return typeof featureId === "number" ? featureId : null
    }

    const getResultAt = (index: number) => data.peek()?.results[index] ?? null

    const onLayerClick = (e: MapLayerMouseEvent) => {
      const featureIndex = getFeatureIndex(e)
      if (featureIndex === null) return

      const result = getResultAt(featureIndex)
      if (!result) return

      const typeSlug = getElementTypeSlug(result.type)
      routerNavigateStrict(`/${typeSlug}/${result.id.toString()}`)
    }

    let hoveredFeatureId: number | null = null
    const onLayerMouseMove = (e: MapLayerMouseEvent) => {
      const featureIndex = getFeatureIndex(e)
      if (featureIndex === null) return

      if (hoveredFeatureId === featureIndex) return
      if (hoveredFeatureId === null) setMapHover(map, LAYER_ID)
      hoveredFeatureId = featureIndex
      setHoveredIndex(featureIndex, true)
    }

    const onLayerMouseLeave = () => {
      hoveredFeatureId = null
      clearMapHover(map, LAYER_ID)
      setHoveredIndex(null)
    }

    map.on("click", LAYER_ID, onLayerClick)
    map.on("mousemove", LAYER_ID, onLayerMouseMove)
    map.on("mouseleave", LAYER_ID, onLayerMouseLeave)

    return () => {
      map.off("click", LAYER_ID, onLayerClick)
      map.off("mousemove", LAYER_ID, onLayerMouseMove)
      map.off("mouseleave", LAYER_ID, onLayerMouseLeave)

      setHoveredIndex(null)
      focusObjects(map)
      clearMapHover(map, LAYER_ID)
      source.setData(emptyFeatureCollection)
      removeMapLayer(map, LAYER_ID)
    }
  })

  // Effect: route view sync.
  useSignalEffect(() => {
    const view = route.value?.at
    if (!view) return

    const { lng, lat } = map.getCenter()
    const currentView = encodeMapState({ lon: lng, lat, zoom: map.getZoom() }, "")
    const routeView = encodeMapState(view, "")
    if (currentView === routeView) return

    map.jumpTo({ center: [view.lon, view.lat], zoom: view.zoom })
  })

  // Effect: active route with no URL should clear any stale markers/focus.
  useSignalEffect(() => {
    if (!active.value) return
    const u = url.value
    if (u !== null) return

    setHoveredIndex(null)
    entryRefs.current.length = 0
    elementsByIndex.current = []
    source.setData(emptyFeatureCollection)
    searchThisAreaVisible.value = false
  })

  // Effect: on each successful load, update markers + initial focus + "search this area" alert.
  useSignalEffect(() => {
    if (!active.value) return

    const d = data.value
    if (!d) return

    // Clear any existing hover state before replacing data.
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
        coordinates: [result.lon, result.lat],
      },
    }))
    source.setData({ type: "FeatureCollection", features })

    // Prepare the "search this area" alert.
    searchThisAreaVisible.value = false

    let initialBounds: LngLatBounds | null = null
    const onMapZoomOrMoveEnd = () => {
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
      map.off("moveend", onMapZoomOrMoveEnd)
    }
    map.on("moveend", onMapZoomOrMoveEnd)

    const currentRoute = route.peek()
    if (currentRoute?.tag !== "where-is-this") {
      const b = d.bounds
      if (b) {
        const boundsPadded = boundsPadding(
          new LngLatBounds([b.minLon, b.minLat, b.maxLon, b.maxLat]),
          0.05,
        )
        console.debug("Search: Focusing on bounds", boundsPadded)
        map.fitBounds(boundsPadded, { maxZoom: 14 })
      } else if (d.results.length) {
        const [first, ...rest] = d.results
        const markersBounds = rest.reduce(
          (bounds, r) => bounds.extend([r.lon, r.lat]),
          new LngLatBounds([first.lon, first.lat, first.lon, first.lat]),
        )
        const boundsPadded = boundsPadding(markersBounds, 0.15)
        console.debug("Search: Focusing on results", boundsPadded)
        map.fitBounds(boundsPadded, { maxZoom: 14 })
      }
    }

    return () => {
      searchThisAreaVisible.value = false
      map.off("moveend", onMapZoomOrMoveEnd)
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

/** Create a new search controller */
export const getSearchController = (map: MaplibreMap) => {
  const source = map.getSource<GeoJSONSource>(LAYER_ID)
  assertExists(source)

  const sidebar = getActionSidebar("search")
  const searchForm = document.getElementById("SearchForm")
  assertExists(searchForm)

  const route = signal<SearchRoute>(null)
  const searchThisAreaVisible = signal(false)

  const onSearchThisAreaClick = () => {
    console.debug("Search: New area clicked")
    searchThisAreaVisible.value = false

    const current = route.peek()
    if (!current) return

    const { lng, lat } = map.getCenter()
    const at = encodeMapState({ lon: lng, lat, zoom: map.getZoom() }, "")

    if (current.tag === "where-is-this") {
      routerNavigateStrict(`/search${qsEncode({ at })}`)
      return
    }

    if (!current.query) return

    routerNavigateStrict(
      `/search${qsEncode({
        q: current.query,
        at,
        local: current.localOnly ? "1" : undefined,
      })}`,
    )
  }

  mountMapAlert(
    <SearchThisAreaAlert
      visible={searchThisAreaVisible}
      onClick={onSearchThisAreaClick}
    />,
  )

  render(
    <SearchSidebar
      map={map}
      source={source}
      sidebar={sidebar}
      searchForm={searchForm}
      route={route}
      searchThisAreaVisible={searchThisAreaVisible}
    />,
    sidebar,
  )

  return {
    load: () => {
      const searchParams = qsParse(window.location.search)
      const query = searchParams.q || searchParams.query || ""
      const at = parseLonLatZoom(searchParams)
      const localOnly = searchParams.local !== undefined

      if (query) {
        route.value = { tag: "query", query, localOnly, at }
      } else if (at) {
        route.value = { tag: "where-is-this", at }
      } else {
        route.value = { tag: "query", query: "", localOnly: false, at: null }
      }
    },
    unload: (newPath?: string) => {
      if (newPath?.startsWith("/search")) return
      route.value = null
      searchThisAreaVisible.value = false
    },
  }
}
