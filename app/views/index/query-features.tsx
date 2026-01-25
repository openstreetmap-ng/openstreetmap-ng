import {
  SidebarHeader,
  SidebarResourceBody,
  useSidebarRpc,
} from "@index/_action-sidebar"
import { defineRoute } from "@index/router"
import { queryParam } from "@lib/codecs"
import { prefersReducedMotion } from "@lib/config"
import { useDisposeEffect, useDisposeSignalEffect } from "@lib/dispose-scope"
import { type FocusLayerPaint, focusObjects } from "@lib/map/layers/focus-layer"
import {
  emptyFeatureCollection,
  getExtendedLayerId,
  type LayerId,
  layersConfig,
} from "@lib/map/layers/layers"
import { convertRenderElementsData } from "@lib/map/render-objects"
import type { LonLat, LonLatZoom } from "@lib/map/state"
import {
  type NearbyResponse_ResultValid,
  QueryFeaturesService,
} from "@lib/proto/query_features_pb"
import { setPageTitle } from "@lib/title"
import { type Signal, useComputed, useSignalEffect } from "@preact/signals"
import { toTitleCase } from "@std/text/unstable-to-title-case"
import type { FeatureCollection } from "geojson"
import { t } from "i18next"
import type { GeoJSONSource, Map as MaplibreMap } from "maplibre-gl"
import { ElementResultEntry } from "./search"

export const QUERY_FEATURES_MIN_ZOOM = 14

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

const getQueryAt = (at: LonLatZoom | undefined): LonLatZoom | null =>
  at
    ? {
        lon: at.lon,
        lat: at.lat,
        zoom: Math.round(Math.max(at.zoom, QUERY_FEATURES_MIN_ZOOM)),
      }
    : null

const QueryFeaturesResultsList = ({
  map,
  results,
}: {
  map: MaplibreMap
  results: NearbyResponse_ResultValid[]
}) => {
  const focusEntries = results.map((entry) => convertRenderElementsData(entry.render))

  const clearFocus = () => focusObjects(map)
  const focusEntryAt = (index: number) =>
    focusObjects(map, focusEntries[index], focusPaint)

  return results.length ? (
    <ul class="search-list list-unstyled mb-0">
      {results.map((result, i) => (
        <ElementResultEntry
          key={`${result.type}:${result.id}`}
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
  at,
}: {
  map: MaplibreMap
  at: Signal<LonLatZoom | undefined>
}) => {
  const source = map.getSource<GeoJSONSource>(LAYER_ID)!

  const titleText = toTitleCase(t("javascripts.site.queryfeature_tooltip"))
  setPageTitle(titleText)

  const queryAt = useComputed(() => getQueryAt(at.value))

  const { resource } = useSidebarRpc(
    useComputed(() => {
      const p = queryAt.value
      return p ? { at: p } : null
    }),
    QueryFeaturesService.method.nearby,
  )

  // Effect: Map layer lifecycle.
  useDisposeEffect((scope) => {
    scope.mapLayerLifecycle(map, LAYER_ID, false)
    scope.defer(() => {
      focusObjects(map)
    })
  }, [])

  // Effect: Focus on the query position if it's offscreen.
  useSignalEffect(() => {
    const p = queryAt.value
    if (!p || map.getBounds().contains(p)) return
    map.jumpTo({ center: p, zoom: p.zoom })
  })

  // Effect: Show query radius animation on each new position.
  useDisposeSignalEffect((scope) => {
    const p = queryAt.value
    if (!p) return

    const radiusMeters = 10 * 1.5 ** (19 - p.zoom)
    source.setData(getCircleFeature(p, radiusMeters))

    // Fade out circle smoothly
    const animationDuration = 750
    const fillLayerId = getExtendedLayerId(LAYER_ID, "fill")
    const lineLayerId = getExtendedLayerId(LAYER_ID, "line")

    scope.frame(({ time, startTime, next }) => {
      const elapsedTime = time - startTime
      let opacity = 1 - Math.min(elapsedTime / animationDuration, 1)
      if (prefersReducedMotion()) opacity = opacity > 0 ? 1 : 0

      map.setPaintProperty(fillLayerId, "fill-opacity", opacity * 0.4)
      map.setPaintProperty(lineLayerId, "line-opacity", opacity)

      if (opacity > 0) return next()

      source.setData(emptyFeatureCollection)
    })()

    scope.defer(() => {
      source.setData(emptyFeatureCollection)
    })
  })

  return (
    <div class="sidebar-content">
      <div class="section">
        <SidebarHeader title={titleText} />
        <p>{t("browse.query.introduction")}</p>
        <h4 class="mb-3">{t("browse.query.nearby")}</h4>

        {queryAt.value ? (
          <SidebarResourceBody resource={resource}>
            {(d) => (
              <QueryFeaturesResultsList
                map={map}
                results={d.results}
              />
            )}
          </SidebarResourceBody>
        ) : (
          <QueryFeaturesResultsList
            map={map}
            results={[]}
          />
        )}
      </div>
    </div>
  )
}

export const QueryFeaturesRoute = defineRoute({
  id: "query-features",
  path: "/query",
  query: { at: queryParam.lonLatZoom() },
  Component: QueryFeaturesSidebar,
})

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
