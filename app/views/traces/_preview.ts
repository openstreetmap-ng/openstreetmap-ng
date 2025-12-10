import { padLngLatBounds } from "@lib/map/bounds"
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
import { requestAnimationFramePolyfill } from "@lib/polyfills"
import { decodeLonLat } from "@lib/polyline"
import { roundTo } from "@std/math/round-to"
import type { LineString } from "geojson"
import {
    type GeoJSONSource,
    LngLatBounds,
    Map as MaplibreMap,
    ScaleControl,
} from "maplibre-gl"

const LAYER_ID = "trace-preview" as LayerId
const LAYER_ID_ANT = "trace-preview-ant" as LayerId

const ANT_DURATION = 2000
const ANT_DASH_A = 4
const ANT_DASH_B = 3
const ANT_DASH_LENGTH = ANT_DASH_A + ANT_DASH_B

const tracePreviewContainer = document.querySelector("div.trace-preview")
if (tracePreviewContainer) {
    console.debug("Initializing trace preview map")

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
                // buggy with line-dasharray: "line-cap": "round",
            },
            paint: {
                "line-color": "#220",
                "line-width": 4.5,
            },
        },
    })

    const map = new MaplibreMap({
        container: tracePreviewContainer,
        maxZoom: 19,
        attributionControl: { compact: true, customAttribution: "" },
        refreshExpiredTiles: false,
    })
    configureDefaultMapBehavior(map)
    addMapLayerSources(map, "all")

    const isSmall = tracePreviewContainer.classList.contains("trace-preview-sm")
    if (!isSmall) {
        map.addControl(new ScaleControl({ unit: "imperial" }))
        map.addControl(new ScaleControl({ unit: "metric" }))
        addControlGroup(map, [new CustomZoomControl(), new CustomGeolocateControl()])
    } else {
        addControlGroup(map, [new CustomZoomControl()])
    }

    addMapLayer(map, DEFAULT_LAYER_ID)
    addMapLayer(map, LAYER_ID)
    addMapLayer(map, LAYER_ID_ANT)

    // Add trace path
    const coordinates = decodeLonLat(tracePreviewContainer.dataset.line!, 6)
    const bounds = coordinates.reduce(
        (bounds, coord) => bounds.extend(coord),
        new LngLatBounds(),
    )
    map.fitBounds(padLngLatBounds(bounds, 0.3), { animate: false })

    const geometry: LineString = { type: "LineString", coordinates }
    map.getSource<GeoJSONSource>(LAYER_ID)!.setData(geometry)
    map.getSource<GeoJSONSource>(LAYER_ID_ANT)!.setData(geometry)

    let lastOffset = -1

    const antPath = (timestamp: DOMHighResTimeStamp) => {
        const progress = (timestamp % ANT_DURATION) / ANT_DURATION
        const offset = roundTo(progress * ANT_DASH_LENGTH, 1)
        if (offset !== lastOffset) {
            lastOffset = offset
            // https://docs.mapbox.com/mapbox-gl-js/example/animate-ant-path/
            const dashPattern: number[] =
                offset <= ANT_DASH_B //
                    ? [offset, ANT_DASH_A, ANT_DASH_B - offset]
                    : [0, offset - ANT_DASH_B, ANT_DASH_B, ANT_DASH_LENGTH - offset]
            map.setPaintProperty(LAYER_ID_ANT, "line-dasharray", dashPattern)
        }
        requestAnimationFramePolyfill(antPath)
    }
    requestAnimationFramePolyfill(antPath)
}
