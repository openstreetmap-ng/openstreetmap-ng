import {
  getActionSidebar,
  SidebarHeader,
  SidebarResourceBody,
  switchActionSidebar,
  useSidebarFetch,
} from "@index/_action-sidebar"
import { prefersReducedMotion } from "@lib/config"
import { isLatitude, isLongitude, isZoom } from "@lib/coords"
import { QUERY_FEATURES_MIN_ZOOM } from "@lib/map/controls/query-features"
import { type FocusLayerPaint, focusObjects } from "@lib/map/layers/focus-layer"
import {
  addMapLayer,
  emptyFeatureCollection,
  getExtendedLayerId,
  type LayerId,
  layersConfig,
  removeMapLayer,
} from "@lib/map/layers/layers"
import { convertRenderElementsData } from "@lib/map/render-objects"
import type { LonLat, LonLatZoom } from "@lib/map/state"
import { requestAnimationFramePolyfill } from "@lib/polyfills"
import {
  type QueryFeaturesNearbyData_Result,
  QueryFeaturesNearbyDataSchema,
} from "@lib/proto/shared_pb"
import { qsEncode, qsParse } from "@lib/qs"
import { setPageTitle } from "@lib/title"
import {
  type ReadonlySignal,
  signal,
  useComputed,
  useSignalEffect,
} from "@preact/signals"
import { assertExists } from "@std/assert"
import { toTitleCase } from "@std/text/unstable-to-title-case"
import type { FeatureCollection } from "geojson"
import { t } from "i18next"
import { type GeoJSONSource, LngLat, type Map as MaplibreMap } from "maplibre-gl"
import { render } from "preact"
import { ElementResultEntry } from "./search"

const LAYER_ID = "query-features" as LayerId
const THEME_COLOR = "#f60"
layersConfig.set(LAYER_ID, {
  specification: {
    type: "geojson",
    data: emptyFeatureCollection,
  },
  layerTypes: ["fill", "line"],
  layerOptions: {
    paint: {
      "fill-opacity": 0,
      "fill-color": THEME_COLOR,
      "line-opacity": 0,
      "line-color": THEME_COLOR,
      "line-width": 4,
    },
  },
  priority: 170,
})

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

const getURLQueryPosition = (map: MaplibreMap) => {
  const searchParams = qsParse(window.location.search)
  if (!(searchParams.lon && searchParams.lat)) return null

  const lon = Number.parseFloat(searchParams.lon)
  const lat = Number.parseFloat(searchParams.lat)
  const zoom = Math.max(
    searchParams.zoom ? Number.parseFloat(searchParams.zoom) : map.getZoom(),
    QUERY_FEATURES_MIN_ZOOM,
  )

  return isLongitude(lon) && isLatitude(lat) && isZoom(zoom)
    ? { lon, lat, zoom: zoom | 0 }
    : null
}

const QueryFeaturesResultsList = ({
  map,
  results,
}: {
  map: MaplibreMap
  results: QueryFeaturesNearbyData_Result[]
}) => {
  const focusEntries = results.map((entry) => convertRenderElementsData(entry.render))

  const clearFocus = () => focusObjects(map)
  const focusEntryAt = (index: number) =>
    focusObjects(map, focusEntries[index], focusPaint)

  return results.length ? (
    <ul class="search-list list-unstyled mb-0">
      {results.map((result, i) => (
        <ElementResultEntry
          key={`${result.type}:${result.id.toString()}`}
          result={result}
          onFocus={() => focusEntryAt(i)}
          onBlur={() => clearFocus()}
        />
      ))}
    </ul>
  ) : (
    <p>{t("javascripts.query.nothing_found")}</p>
  )
}

const QueryFeaturesSidebar = ({
  map,
  source,
  sidebar,
  active,
  position,
}: {
  map: MaplibreMap
  source: GeoJSONSource
  sidebar: HTMLElement
  active: ReadonlySignal<boolean>
  position: ReadonlySignal<LonLatZoom | null>
}) => {
  const titleText = toTitleCase(t("javascripts.site.queryfeature_tooltip"))

  const queryPosition = useComputed(() => (active.value ? position.value : null))

  const url = useComputed(() => {
    const p = queryPosition.value
    if (!p) return null
    return `/api/web/query-features/nearby${qsEncode({
      lon: p.lon.toString(),
      lat: p.lat.toString(),
      zoom: p.zoom.toString(),
    })}`
  })

  const { resource } = useSidebarFetch(url, QueryFeaturesNearbyDataSchema)

  // Effect: Sidebar visibility + title + map layer lifecycle.
  useSignalEffect(() => {
    if (!active.value) return
    switchActionSidebar(map, sidebar)
    setPageTitle(titleText)
    addMapLayer(map, LAYER_ID, false)

    return () => {
      removeMapLayer(map, LAYER_ID, false)
      source.setData(emptyFeatureCollection)
      focusObjects(map)
    }
  })

  // Effect: Focus on the query position if it's offscreen.
  useSignalEffect(() => {
    const p = queryPosition.value
    if (!p) return

    const center = new LngLat(p.lon, p.lat)
    if (!map.getBounds().contains(center)) {
      map.jumpTo({ center, zoom: p.zoom })
    }
  })

  // Effect: Show query radius animation on each new position.
  useSignalEffect(() => {
    const p = queryPosition.value
    if (!p) return

    const abortController = new AbortController()
    animateQueryRadius(map, source, p, abortController.signal)
    return () => abortController.abort()
  })

  return (
    <div class="sidebar-content">
      <div class="section">
        <SidebarHeader title={titleText} />
        <p>{t("browse.query.introduction")}</p>
        <h4 class="mb-3">{t("browse.query.nearby")}</h4>

        <SidebarResourceBody resource={resource}>
          {(d) => (
            <QueryFeaturesResultsList
              map={map}
              results={d.results}
            />
          )}
        </SidebarResourceBody>
      </div>
    </div>
  )
}

export const getQueryFeaturesController = (map: MaplibreMap) => {
  const source = map.getSource<GeoJSONSource>(LAYER_ID)
  assertExists(source)

  const sidebar = getActionSidebar("query-features")
  const active = signal(false)
  const position = signal<LonLatZoom | null>(null)

  render(
    <QueryFeaturesSidebar
      map={map}
      source={source}
      sidebar={sidebar}
      active={active}
      position={position}
    />,
    sidebar,
  )

  const queryFeaturesButton = map
    .getContainer()
    .querySelector(".maplibregl-ctrl.query-features button")
  assertExists(queryFeaturesButton)

  return {
    load: () => {
      active.value = true
      position.value = getURLQueryPosition(map)
    },
    unload: (newPath?: string) => {
      if (!newPath?.startsWith("/query")) {
        if (queryFeaturesButton.classList.contains("active")) {
          console.debug("QueryFeatures: Deactivating button")
          queryFeaturesButton.click()
        }

        active.value = false
        position.value = null
      }
    },
  }
}

const animateQueryRadius = (
  map: MaplibreMap,
  source: GeoJSONSource,
  position: LonLatZoom,
  abortSignal: AbortSignal,
) => {
  const radiusMeters = 10 * 1.5 ** (19 - position.zoom)
  console.debug("QueryFeatures: Radius", radiusMeters, "meters")

  source.setData(getCircleFeature(position, radiusMeters))

  // Fade out circle smoothly
  const animationDuration = 750
  const fillLayerId = getExtendedLayerId(LAYER_ID, "fill")
  const lineLayerId = getExtendedLayerId(LAYER_ID, "line")

  let animationStart = performance.now()
  const fadeOut = (timestamp: DOMHighResTimeStamp) => {
    if (abortSignal.aborted) return

    if (timestamp < animationStart) animationStart = timestamp
    const elapsedTime = timestamp - animationStart
    let opacity = 1 - Math.min(elapsedTime / animationDuration, 1)
    if (prefersReducedMotion()) opacity = opacity > 0 ? 1 : 0

    map.setPaintProperty(fillLayerId, "fill-opacity", opacity * 0.4)
    map.setPaintProperty(lineLayerId, "line-opacity", opacity)

    if (opacity > 0) {
      requestAnimationFramePolyfill(fadeOut)
      return
    }

    source.setData(emptyFeatureCollection)
  }
  requestAnimationFramePolyfill(fadeOut)
}

const getCircleFeature = (
  { lon, lat }: LonLat,
  radiusMeters: number,
  vertices = 36,
): FeatureCollection => {
  const radiusLat = metersToDegrees(radiusMeters)
  const radiusLon = radiusLat / Math.cos((lat * Math.PI) / 180)
  const coords: number[][] = []

  const delta = (2 * Math.PI) / vertices
  const cosDelta = Math.cos(delta)
  const sinDelta = Math.sin(delta)
  let cosTheta = 1 // cos(0) = 1
  let sinTheta = 0 // sin(0) = 0

  for (let i = 0; i < vertices; i++) {
    const x = lon + radiusLon * cosTheta
    const y = lat + radiusLat * sinTheta
    coords.push([x, y])

    const newCosTheta = cosTheta * cosDelta - sinTheta * sinDelta
    const newSinTheta = sinTheta * cosDelta + cosTheta * sinDelta
    cosTheta = newCosTheta
    sinTheta = newSinTheta
  }
  coords.push(coords[0])

  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: {},
        geometry: {
          type: "LineString",
          coordinates: coords,
        },
      },
      {
        type: "Feature",
        properties: {},
        geometry: {
          type: "Polygon",
          coordinates: [coords],
        },
      },
    ],
  }
}

const metersToDegrees = (meters: number) => meters / (6371000 / 57.29577951308232) // R / (180 / pi)
