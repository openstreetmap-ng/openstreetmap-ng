import { useDisposeLayoutEffect } from "@lib/dispose-scope"
import { boundsPadding } from "@lib/map/bounds"
import { configureMap } from "@lib/map/configure-map"
import { CustomGeolocateControl } from "@lib/map/controls/geolocate"
import { addControlGroup } from "@lib/map/controls/group"
import { CustomZoomControl } from "@lib/map/controls/zoom"
import { configureDefaultMapBehavior } from "@lib/map/defaults"
import {
  addMapLayer,
  addMapLayerSources,
  DEFAULT_LAYER_ID,
  emptyFeatureCollection,
  type LayerId,
  layersConfig,
} from "@lib/map/layers/layers"
import { polylineDecode } from "@lib/polyline"
import type { LineString } from "geojson"
import { type GeoJSONSource, LngLatBounds, ScaleControl } from "maplibre-gl"
import { useRef } from "preact/hooks"
import { getAntDashFrames } from "./_map-preview.macro" with { type: "macro" }
import { traceMotionDuration } from "./_motion"

const LAYER_ID = "trace-preview" as LayerId
const LAYER_ID_ANT = "trace-preview-ant" as LayerId
const ANT_DURATION = 2000
const ANT_DASH_FRAMES = getAntDashFrames()
const ANT_DASH_INITIAL_FRAME = ANT_DASH_FRAMES[0]!

layersConfig.set(LAYER_ID, {
  specification: {
    type: "geojson",
    data: emptyFeatureCollection,
  },
  layerTypes: ["line"],
  layerOptions: {
    layout: {
      "line-join": "round",
      "line-cap": "round",
    },
    paint: {
      "line-color": "#f60",
      "line-width": 4.5,
    },
  },
})

layersConfig.set(LAYER_ID_ANT, {
  specification: {
    type: "geojson",
    data: emptyFeatureCollection,
  },
  layerTypes: ["line"],
  layerOptions: {
    layout: {
      "line-join": "round",
    },
    paint: {
      "line-color": "#220",
      "line-width": 4.5,
      "line-dasharray": ANT_DASH_INITIAL_FRAME,
    },
  },
})

export const MapPreview = ({
  class: className,
  line,
  small = false,
}: {
  class: string
  line: string
  small?: boolean
}) => {
  const ref = useRef<HTMLDivElement>(null)

  useDisposeLayoutEffect(
    (scope) => {
      const map = configureMap({
        container: ref.current!,
        maxZoom: 19,
        attributionControl: { compact: true, customAttribution: "" },
        refreshExpiredTiles: false,
      })
      if (!map) return

      scope.defer(() => map.remove())

      configureDefaultMapBehavior(map)
      addMapLayerSources(map, "all")
      if (small) {
        addControlGroup(map, [new CustomZoomControl()])
      } else {
        map.addControl(new ScaleControl({ unit: "imperial" }))
        map.addControl(new ScaleControl({ unit: "metric" }))
        addControlGroup(map, [new CustomZoomControl(), new CustomGeolocateControl()])
      }

      addMapLayer(map, DEFAULT_LAYER_ID)
      addMapLayer(map, LAYER_ID)
      addMapLayer(map, LAYER_ID_ANT)

      const coordinates = polylineDecode(line, 6)
      if (!coordinates.length) return

      const bounds = coordinates.reduce(
        (currentBounds, coord) => currentBounds.extend(coord),
        new LngLatBounds(),
      )
      map.fitBounds(boundsPadding(bounds, 0.3), { animate: false })

      const geometry: LineString = { type: "LineString", coordinates }
      map.getSource<GeoJSONSource>(LAYER_ID)!.setData(geometry)
      map.getSource<GeoJSONSource>(LAYER_ID_ANT)!.setData(geometry)

      const duration = traceMotionDuration(ANT_DURATION)
      let lastFrameIndex = 0
      const animate = scope.frame(({ time, startTime, next }) => {
        const progress = ((time - startTime) % duration) / duration
        const frameIndex = Math.floor(progress * ANT_DASH_FRAMES.length)
        if (frameIndex !== lastFrameIndex) {
          lastFrameIndex = frameIndex
          map.setPaintProperty(
            LAYER_ID_ANT,
            "line-dasharray",
            ANT_DASH_FRAMES[frameIndex],
          )
        }
        next()
      })
      animate()
    },
    [line, small],
  )

  return (
    <div
      ref={ref}
      class={`trace-preview ${small ? "trace-preview-sm" : ""} ${className}`}
    />
  )
}
