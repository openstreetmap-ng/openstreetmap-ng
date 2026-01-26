import { SidebarHeader } from "@index/_action-sidebar"
import { defineRoute } from "@index/router"
import { queryParam } from "@lib/codecs"
import { formatPoint, tryParsePoint, zoomPrecision } from "@lib/coords"
import { useDisposeEffect } from "@lib/dispose-scope"
import {
  formatDistance,
  formatDistanceRounded,
  formatHeight,
  formatTime,
} from "@lib/format"
import { tRich } from "@lib/i18n"
import { routingEngineStorage } from "@lib/local-storage"
import { boundsToString, fitBoundsIfNeeded } from "@lib/map/bounds"
import { clearMapHover, setMapHover } from "@lib/map/hover"
import {
  emptyFeatureCollection,
  type LayerId,
  layersConfig,
} from "@lib/map/layers/layers"
import { getMarkerIconElement, MARKER_ICON_ANCHOR } from "@lib/map/marker"
import { requestAnimationFramePolyfill } from "@lib/polyfills"
import { polylineDecode } from "@lib/polyline"
import {
  type RoutingResult_AttributionValid,
  type RoutingResult_EndpointValid,
  RoutingResultSchema,
  type RoutingResultValid,
} from "@lib/proto/shared_pb"
import { scrollElementIntoView } from "@lib/scroll"
import { configureStandardForm } from "@lib/standard-form"
import { setPageTitle } from "@lib/title"
import type { Bounds } from "@lib/types"
import { type Signal, useSignal, useSignalEffect } from "@preact/signals"
import { memoize } from "@std/cache/memoize"
import type { Feature, FeatureCollection, LineString } from "geojson"
import { t } from "i18next"
import {
  type GeoJSONSource,
  LngLat,
  LngLatBounds,
  type LngLatLike,
  type MapGeoJSONFeature,
  type Map as MaplibreMap,
  Marker,
  Point,
  Popup,
} from "maplibre-gl"
import { useId, useRef } from "preact/hooks"

const LAYER_ID = "routing" as LayerId
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
      "line-color": ["case", ["boolean", ["get", "base"], false], "#03f", "#ff0"],
      "line-opacity": [
        "case",
        ["boolean", ["get", "base"], false],
        0.3, // Complete route is always 0.3 opacity
        ["boolean", ["feature-state", "hover"], false],
        0.5, // Individual steps are 0.5 when hovered
        0, // Individual steps are invisible when not hovered
      ],
      "line-width": 10,
    },
  },
  priority: 110,
})

const DRAG_DATA_TYPE = "text/osm-routing-direction"
const DRAG_IMAGE_WIDTH = 25
const DRAG_IMAGE_HEIGHT = 41
const DRAG_IMAGE_OFFSET_X = 12
const DRAG_IMAGE_OFFSET_Y = 21

const ROUTING_ENGINES = memoize(() => [
  ["graphhopper_car", t("javascripts.directions.engines.graphhopper_car")],
  ["osrm_car", t("javascripts.directions.engines.fossgis_osrm_car")],
  ["valhalla_auto", t("javascripts.directions.engines.fossgis_valhalla_car")],
  ["graphhopper_bike", t("javascripts.directions.engines.graphhopper_bicycle")],
  ["osrm_bike", t("javascripts.directions.engines.fossgis_osrm_bike")],
  ["valhalla_bicycle", t("javascripts.directions.engines.fossgis_valhalla_bicycle")],
  ["graphhopper_foot", t("javascripts.directions.engines.graphhopper_foot")],
  ["osrm_foot", t("javascripts.directions.engines.fossgis_osrm_foot")],
  ["valhalla_pedestrian", t("javascripts.directions.engines.fossgis_valhalla_foot")],
])

export const ROUTING_QUERY_PRECISION = zoomPrecision(19)

type RouteInstructionView = {
  iconNum: number
  text: string
  distanceText: string
  point: [number, number]
  segmentBounds: LngLatBounds
}

type RouteElevationView = {
  ascendText: string
  descendText: string
}

type RouteView = {
  distanceText: string
  timeText: string
  elevation: RouteElevationView | null
  instructions: RouteInstructionView[]
  attribution: RoutingResult_AttributionValid
}

type LoadedEndpoint = {
  query: string
  label: string
  lon: number
  lat: number
}

const ENDPOINT_DIRS = ["start", "end"] as const

type EndpointDir = (typeof ENDPOINT_DIRS)[number]

const isEndpointDir = (value: unknown): value is EndpointDir =>
  ENDPOINT_DIRS.includes(value as EndpointDir)

type EndpointState = {
  marker: Marker | null
  loaded: LoadedEndpoint | null
}

const findInstructionId = (features: MapGeoJSONFeature[] | undefined) => {
  if (features)
    for (const feature of features) {
      const { id } = feature
      // We index segment features by the instruction they lead into (1..N-1).
      if (typeof id === "number" && id > 0) return id
    }
  return null
}

const computeRouteRender = (route: RoutingResultValid) => {
  const features: Feature<LineString>[] = []
  const allCoords = polylineDecode(route.line, route.lineQuality)

  if (allCoords.length)
    features.push({
      type: "Feature",
      id: -1,
      properties: { base: true },
      geometry: { type: "LineString", coordinates: allCoords },
    })

  const instructions: RouteInstructionView[] = []
  let totalDistance = 0
  let totalTime = 0
  let coordsSliceStart = 0
  let prevSegmentBounds: LngLatBounds | undefined

  const lastStepIndex = route.steps.length - 1

  for (const [stepIndex, step] of route.steps.entries()) {
    totalDistance += step.distance
    totalTime += step.time

    const stepCoords = allCoords.slice(
      coordsSliceStart,
      coordsSliceStart + (step.numCoords || 1),
    )
    if (step.numCoords) coordsSliceStart += step.numCoords - 1

    const point = stepCoords[0]
    const pointBounds = new LngLatBounds([point, point])

    instructions.push({
      iconNum: step.iconNum,
      text: step.text,
      distanceText: formatDistanceRounded(step.distance),
      point,
      segmentBounds: prevSegmentBounds ?? pointBounds,
    })

    if (stepCoords.length > 1) {
      prevSegmentBounds = stepCoords.reduce(
        (bounds, coord) => bounds.extend(coord),
        new LngLatBounds(),
      )
      if (stepIndex < lastStepIndex)
        features.push({
          type: "Feature",
          id: stepIndex + 1,
          properties: {},
          geometry: { type: "LineString", coordinates: stepCoords },
        })
    } else {
      prevSegmentBounds = pointBounds
    }
  }

  return {
    featureCollection: {
      type: "FeatureCollection",
      features,
    } satisfies FeatureCollection,
    view: {
      distanceText: formatDistance(totalDistance),
      timeText: formatTime(totalTime),
      elevation: route.elevation
        ? {
            ascendText: formatHeight(route.elevation.ascend),
            descendText: formatHeight(route.elevation.descend),
          }
        : null,
      instructions,
      attribution: route.attribution,
    } satisfies RouteView,
  }
}

const RoutingAttribution = ({
  attribution,
}: {
  attribution: RoutingResult_AttributionValid
}) => {
  return (
    <div class="attribution">
      {tRich("javascripts.directions.instructions.courtesy", {
        link: () => (
          <a
            href={attribution.href}
            target="_blank"
            rel="noopener noreferrer"
          >
            {attribution.label}
          </a>
        ),
      })}
    </div>
  )
}

const RoutingSidebar = ({
  map,
  engine,
  from,
  to,
}: {
  map: MaplibreMap
  engine: Signal<string | undefined>
  from: Signal<string | undefined>
  to: Signal<string | undefined>
}) => {
  setPageTitle(t("javascripts.directions.directions"))
  const mapContainer = map.getContainer()
  const source = map.getSource<GeoJSONSource>(LAYER_ID)!

  const loading = useSignal(false)
  const routeView = useSignal<RouteView | null>(null)
  const activeInstructionId = useSignal<number | null>(null)
  const activeFeatureIdRef = useRef<number | null>(null)
  const formRef = useRef<HTMLFormElement>(null)

  const engineInputId = useId()

  const startInputId = useId()
  const startDisplay = useSignal(from.peek() ?? "")

  const endInputId = useId()
  const endDisplay = useSignal(to.peek() ?? "")

  const endpoints = useRef<Record<EndpointDir, EndpointState>>({
    start: { marker: null, loaded: null },
    end: { marker: null, loaded: null },
  })

  const popup = useRef<Popup | null>(null)
  const popupContent = useRef<{
    root: HTMLDivElement
    number: HTMLSpanElement
    instruction: HTMLSpanElement
  } | null>(null)

  const sidebarPointerRef = useRef<[number, number] | null>(null)

  const parentSidebar = document
    .getElementById("ActionSidebar")!
    .closest("div.sidebar")!

  const clearRouteResults = () => {
    popup.current?.remove()
    focusInstruction(null)
    clearMapHover(map, LAYER_ID)
    routeView.value = null
    source.setData(emptyFeatureCollection)
  }

  const lastAppliedUrl = useRef<{ from: string | undefined; to: string | undefined }>({
    from: undefined,
    to: undefined,
  })

  const setEndpointDisplay = (dir: EndpointDir, value: string) => {
    if (dir === "start") startDisplay.value = value
    else endDisplay.value = value
  }

  const setUrlEndpoint = (dir: EndpointDir, value: string | undefined) => {
    value ||= undefined
    if (dir === "start") {
      from.value = value
      lastAppliedUrl.current.from = value
    } else {
      to.value = value
      lastAppliedUrl.current.to = value
    }
  }

  const submitFormIfFilled = () => {
    popup.current?.remove()
    if (!(from.peek() && to.peek())) return
    requestAnimationFramePolyfill(() => {
      formRef.current?.requestSubmit()
    })
  }

  // --- Map & Interaction Logic ---

  const setEndpointMarker = (dir: EndpointDir, lngLatLike: LngLatLike) => {
    const lngLat = LngLat.convert(lngLatLike)
    const display = formatPoint(lngLat, zoomPrecision(map.getZoom()))
    const urlValue = formatPoint(lngLat, ROUTING_QUERY_PRECISION)
    const endpoint = endpoints.current[dir]
    endpoint.loaded = {
      query: urlValue,
      label: display,
      lon: lngLat.lng,
      lat: lngLat.lat,
    }
    setEndpointDisplay(dir, display)
    getMarker(dir).setLngLat(lngLat).addTo(map)
    setUrlEndpoint(dir, urlValue)
  }

  const applyResolvedEndpoint = (
    dir: EndpointDir,
    entry: RoutingResult_EndpointValid,
  ) => {
    const query = dir === "start" ? (from.peek() ?? "") : (to.peek() ?? "")
    const label = entry.name || query
    const { lon, lat } = entry.location
    endpoints.current[dir].loaded = { query, label, lon, lat }
    setEndpointDisplay(dir, label)
    getMarker(dir).setLngLat([lon, lat]).addTo(map)
  }

  const getMarker = (dir: EndpointDir) => {
    const endpoint = endpoints.current[dir]
    if (!endpoint.marker) {
      const markerColor = dir === "start" ? "green" : "red"
      const marker = new Marker({
        anchor: MARKER_ICON_ANCHOR,
        element: getMarkerIconElement(markerColor, true),
        draggable: true,
      })
      marker.on("dragend", () => {
        const lngLat = marker.getLngLat()
        console.debug("Routing: Marker drag end", lngLat, dir)
        setEndpointMarker(dir, lngLat)
        submitFormIfFilled()
      })
      endpoint.marker = marker
    }
    return endpoint.marker
  }

  const focusInstruction = (instructionId: number | null, scrollIntoView = false) => {
    const route = routeView.peek()
    const nextId =
      instructionId !== null && route?.instructions[instructionId]
        ? instructionId
        : null
    const prevId = activeInstructionId.peek()
    if (prevId === nextId && !scrollIntoView) return

    activeInstructionId.value = nextId

    const nextFeatureId = nextId
    const prevFeatureId = activeFeatureIdRef.current
    if (prevFeatureId !== nextFeatureId) {
      if (prevFeatureId !== null)
        map.setFeatureState({ source: LAYER_ID, id: prevFeatureId }, { hover: false })
      if (nextFeatureId !== null)
        map.setFeatureState({ source: LAYER_ID, id: nextFeatureId }, { hover: true })
      activeFeatureIdRef.current = nextFeatureId
    }

    if (nextId !== null && scrollIntoView) {
      const row = parentSidebar.querySelector(`li[data-instruction-id="${nextId}"]`)
      scrollElementIntoView(parentSidebar, row)
    }
  }

  const selectInstruction = (instructionId: number) => {
    focusInstruction(instructionId)

    const route = routeView.value
    const instruction = route?.instructions[instructionId]
    if (!instruction) return

    fitBoundsIfNeeded(map, instruction.segmentBounds, {
      padBounds: 0.3,
      maxZoom: 16,
      animate: true,
    })

    popup.current ??= new Popup({
      closeButton: false,
      closeOnClick: false,
      closeOnMove: true,
      anchor: "bottom",
      className: "route-steps",
    })

    const { root, number, instruction: instructionEl } = getOrCreatePopupContent()
    number.textContent = `${instructionId + 1}.`
    instructionEl.textContent = instruction.text
    popup.current.setDOMContent(root).setLngLat(instruction.point).addTo(map)
  }

  const updateEndpoints = (data: RoutingResultValid) => {
    let markerBounds: LngLatBounds | undefined

    const updateEndpoint = (dir: EndpointDir, entry: RoutingResult_EndpointValid) => {
      const { minLon, minLat, maxLon, maxLat } = entry.bounds
      const bounds: Bounds = [minLon, minLat, maxLon, maxLat]

      if (markerBounds) {
        markerBounds.extend(bounds)
      } else {
        markerBounds = new LngLatBounds(bounds)
      }

      applyResolvedEndpoint(dir, entry)
    }

    if (data.start) updateEndpoint("start", data.start)
    if (data.end) updateEndpoint("end", data.end)
    if (markerBounds)
      fitBoundsIfNeeded(map, markerBounds, {
        animate: true,
      })
  }

  const updateRoute = (route: RoutingResultValid) => {
    const { view, featureCollection } = computeRouteRender(route)
    routeView.value = view
    source.setData(featureCollection)
    console.debug("Routing: Loaded", route.steps.length, "steps")
  }

  // --- Handlers ---

  const getOrCreatePopupContent = () => {
    if (popupContent.current) return popupContent.current

    const root = document.createElement("div")
    const number = document.createElement("span")
    number.className = "number"
    const instruction = document.createElement("span")
    instruction.className = "instruction ms-1"
    root.append(number, instruction)

    popupContent.current = { root, number, instruction }
    return popupContent.current
  }

  const onInterfaceMarkerDragStart = (direction: EndpointDir) => (e: DragEvent) => {
    const target = e.currentTarget
    if (!(target instanceof HTMLImageElement)) return
    console.debug("Routing: Interface marker drag start", direction)

    const dt = e.dataTransfer
    if (!dt) return
    dt.effectAllowed = "move"
    dt.setData("text/plain", "")
    dt.setData(DRAG_DATA_TYPE, direction)
    const canvas = document.createElement("canvas")
    canvas.width = DRAG_IMAGE_WIDTH
    canvas.height = DRAG_IMAGE_HEIGHT
    const ctx = canvas.getContext("2d")!
    ctx.drawImage(target, 0, 0, DRAG_IMAGE_WIDTH, DRAG_IMAGE_HEIGHT)
    dt.setDragImage(canvas, DRAG_IMAGE_OFFSET_X, DRAG_IMAGE_OFFSET_Y)
  }

  const onReverseClick = () => {
    console.debug("Routing: Reverse clicked")
    const startValue = startDisplay.value
    const endValue = endDisplay.value
    const startUrl = from.peek()
    const endUrl = to.peek()
    const startLoaded = endpoints.current.start.loaded
    const endLoaded = endpoints.current.end.loaded
    const shouldSwapLoaded =
      startLoaded !== null &&
      endLoaded !== null &&
      startValue === startLoaded.label &&
      endValue === endLoaded.label

    if (shouldSwapLoaded) {
      endpoints.current.start.loaded = endpoints.current.end.loaded
      endpoints.current.end.loaded = startLoaded
    } else {
      endpoints.current.start.loaded = null
      endpoints.current.end.loaded = null
    }

    const startMarker = endpoints.current.start.marker
    const endMarker = endpoints.current.end.marker
    if (shouldSwapLoaded && startMarker && endMarker) {
      const startLngLat = startMarker.getLngLat()
      const endLngLat = endMarker.getLngLat()
      startMarker.setLngLat(endLngLat)
      endMarker.setLngLat(startLngLat)
    }

    setEndpointDisplay("start", endValue)
    setEndpointDisplay("end", startValue)
    setUrlEndpoint("start", endUrl)
    setUrlEndpoint("end", startUrl)
    submitFormIfFilled()
  }

  const ensureMarkerFromInput = (dir: EndpointDir) => {
    const value = dir === "start" ? from.peek() : to.peek()
    if (!value) return
    const coords = tryParsePoint(value)
    if (!coords) return
    const [lon, lat] = coords
    endpoints.current[dir].loaded = { query: value, label: value, lon, lat }
    getMarker(dir).setLngLat([lon, lat]).addTo(map)
  }

  // --- Effects ---

  const resetState = () => {
    loading.value = false
    clearRouteResults()
    for (const dir of ENDPOINT_DIRS) {
      const endpoint = endpoints.current[dir]
      endpoint.marker?.remove()
      endpoint.marker = null
      endpoint.loaded = null
    }
  }

  // Effect: Main lifecycle
  useDisposeEffect((scope) => {
    scope.mapLayerLifecycle(map, LAYER_ID)
    scope.defer(resetState)

    // Form configuration
    const disposeForm = configureStandardForm<RoutingResultValid>(
      formRef.current,
      (data) => {
        loading.value = false
        console.debug("Routing: Route calculated", data)
        updateEndpoints(data)
        updateRoute(data)
      },
      {
        cancelOnValidationChange: true,
        protobuf: RoutingResultSchema,
        validationCallback: (formData) => {
          clearRouteResults()
          loading.value = true

          const startValue = from.value ?? ""
          const endValue = to.value ?? ""
          const engineValue = routingEngineStorage.value
          formData.set("start", startValue)
          formData.set("end", endValue)
          formData.set("engine", engineValue)

          for (const dir of ENDPOINT_DIRS) {
            const loaded = endpoints.current[dir].loaded
            const requestValue = dir === "start" ? startValue : endValue
            const isLoaded = loaded && requestValue && requestValue === loaded.query
            formData.set(`${dir}_loaded`, isLoaded ? loaded.query : "")
            formData.set(`${dir}_loaded_lon`, isLoaded ? loaded.lon.toFixed(7) : "0")
            formData.set(`${dir}_loaded_lat`, isLoaded ? loaded.lat.toFixed(7) : "0")
          }

          formData.set("bbox", boundsToString(map.getBounds()))
          return null
        },
        errorCallback: () => {
          loading.value = false
        },
      },
    )
    scope.defer(disposeForm)

    // Event listeners
    scope.mapLayer(map, "click", LAYER_ID, (e) => {
      const instructionId = findInstructionId(e.features)
      if (instructionId === null) return
      selectInstruction(instructionId)
    })
    scope.mapLayer(map, "mousemove", LAYER_ID, (e) => {
      const instructionId = findInstructionId(e.features)
      setMapHover(map, LAYER_ID)
      focusInstruction(instructionId, true)
    })
    scope.mapLayer(map, "mouseleave", LAYER_ID, () => {
      clearMapHover(map, LAYER_ID)
      focusInstruction(null)
    })

    scope.dom(mapContainer, "dragover", (e) => e.preventDefault())
    scope.dom(mapContainer, "drop", (e) => {
      e.preventDefault()
      const dragData = e.dataTransfer?.getData(DRAG_DATA_TYPE)
      if (!isEndpointDir(dragData)) return
      const mapRect = mapContainer.getBoundingClientRect()
      const mousePoint = new Point(e.clientX - mapRect.left, e.clientY - mapRect.top)
      setEndpointMarker(dragData, map.unproject(mousePoint))
      submitFormIfFilled()
    })

    scope.dom(
      parentSidebar,
      "pointermove",
      (e) => (sidebarPointerRef.current = [e.clientX, e.clientY]),
    )
    scope.dom(parentSidebar, "pointerleave", () => (sidebarPointerRef.current = null))

    scope.dom(
      parentSidebar,
      "scroll",
      scope.frame(() => {
        const lastPointer = sidebarPointerRef.current
        if (!lastPointer) return

        const [x, y] = lastPointer
        const r = parentSidebar.getBoundingClientRect()
        if (x < r.left || x > r.right || y < r.top || y > r.bottom) return

        const row = document.elementFromPoint(x, y)?.closest("li[data-instruction-id]")
        focusInstruction(row ? Number.parseInt(row.dataset.instructionId!, 10) : null)
      }),
    )
  }, [])

  // Effect: Apply URL params
  useSignalEffect(() => {
    const routingEngine = engine.value
    const engineChanged =
      routingEngine !== undefined && routingEngine !== routingEngineStorage.peek()
    if (engineChanged) {
      if (ROUTING_ENGINES().some(([value]) => value === routingEngine)) {
        routingEngineStorage.value = routingEngine
      } else {
        console.warn("Routing: Unsupported engine", routingEngine)
      }
    }

    const nextStart = from.value ?? ""
    const nextEnd = to.value ?? ""
    const endpointsChanged =
      lastAppliedUrl.current.from !== from.value ||
      lastAppliedUrl.current.to !== to.value
    if (endpointsChanged) {
      resetState()

      setEndpointDisplay("start", nextStart)
      setEndpointDisplay("end", nextEnd)
      lastAppliedUrl.current.from = from.value
      lastAppliedUrl.current.to = to.value

      for (const dir of ENDPOINT_DIRS) ensureMarkerFromInput(dir)
    }

    if (engineChanged || endpointsChanged) submitFormIfFilled()
  })

  const routeValue = routeView.value

  return (
    <div class="sidebar-content">
      <form
        class="section"
        method="POST"
        action="/api/web/routing"
        ref={formRef}
      >
        <SidebarHeader
          class=""
          title={t("javascripts.directions.directions")}
        />

        <div class="d-flex align-items-end mb-1">
          <div class="custom-input-group flex-grow-1 me-2">
            <label for={startInputId}>{t("site.search.from")}</label>
            <input
              id={startInputId}
              type="text"
              class="form-control"
              required
              value={startDisplay}
              onInput={(e) => {
                endpoints.current.start.loaded = null
                const value = e.currentTarget.value
                setEndpointDisplay("start", value)
                setUrlEndpoint("start", value)
              }}
            />
          </div>
          <img
            class="draggable-marker btn btn-light"
            src="/static/img/marker/green.webp"
            alt={t("alt.marker.green")}
            title={t("map.routing.drag_and_drop.start")}
            draggable
            onDragStart={onInterfaceMarkerDragStart("start")}
          />
        </div>

        <div class="d-flex align-items-end mb-1">
          <div class="custom-input-group flex-grow-1 me-2">
            <label for={endInputId}>{t("site.search.to")}</label>
            <input
              id={endInputId}
              type="text"
              class="form-control"
              required
              value={endDisplay}
              onInput={(e) => {
                endpoints.current.end.loaded = null
                const value = e.currentTarget.value
                setEndpointDisplay("end", value)
                setUrlEndpoint("end", value)
              }}
            />
          </div>
          <img
            class="draggable-marker btn btn-light"
            src="/static/img/marker/red.webp"
            alt={t("alt.marker.red")}
            title={t("map.routing.drag_and_drop.end")}
            draggable
            onDragStart={onInterfaceMarkerDragStart("end")}
          />
        </div>

        <button
          class="btn btn-sm btn-link mb-2"
          type="button"
          onClick={onReverseClick}
        >
          <i class="bi bi-arrow-repeat me-1" />
          {t("site.search.reverse_directions_text")}
        </button>

        <div class="row align-items-end g-2 mb-2">
          <div class="col">
            <label
              for={engineInputId}
              class="form-label"
            >
              {t("map.routing.engine.title")}
            </label>
            <select
              id={engineInputId}
              class="form-select format-select"
              required
              value={routingEngineStorage}
              onInput={(e) => {
                routingEngineStorage.value = e.currentTarget.value
                engine.value = routingEngineStorage.value
                submitFormIfFilled()
              }}
            >
              {ROUTING_ENGINES().map(([value, label]) => (
                <option
                  key={value}
                  value={value}
                >
                  {label}
                </option>
              ))}
            </select>
          </div>

          <div class="col-auto">
            <button
              class="btn btn-primary"
              type="submit"
            >
              {t("site.search.submit_text")}
            </button>
          </div>
        </div>
      </form>

      <div class="section">
        {loading.value && (
          <div class="text-center mt-2">
            <output
              class="spinner-border text-body-secondary"
              aria-live="polite"
            >
              <span class="visually-hidden">{t("browse.start_rjs.loading")}</span>
            </output>
          </div>
        )}

        {routeValue && (
          <>
            <div class="route-info mb-3">
              <div class="mb-1">
                <span class="me-2">
                  <i class="bi bi-signpost-2 me-1-5" />
                  <span class="me-1">{t("javascripts.directions.distance")}:</span>
                  <span>{routeValue.distanceText}</span>
                </span>
                <span>
                  <i class="bi bi-stopwatch me-1-5" />
                  <span class="me-1">{t("javascripts.directions.time")}:</span>
                  <span>{routeValue.timeText}</span>
                </span>
              </div>

              {routeValue.elevation && (
                <div class="route-elevation-info">
                  <span class="me-2">
                    <span class="me-1">{t("javascripts.directions.ascend")}:</span>
                    <span>{routeValue.elevation.ascendText}</span>
                  </span>
                  <span>
                    <span class="me-1">{t("javascripts.directions.descend")}:</span>
                    <span>{routeValue.elevation.descendText}</span>
                  </span>
                </div>
              )}
            </div>

            <ol
              class="route-steps list-group list-group-flush list-unstyled mb-4"
              onFocusOut={(e) => {
                const next = e.relatedTarget
                if (next instanceof Node && e.currentTarget.contains(next)) return
                focusInstruction(null)
              }}
              onPointerLeave={(e) => {
                if (e.pointerType === "touch") return
                if (e.currentTarget.contains(document.activeElement)) return
                focusInstruction(null)
              }}
            >
              {routeValue.instructions.map((inst, instId) => (
                <li
                  key={instId}
                  data-instruction-id={instId.toString()}
                  class={`list-group-item p-0 ${
                    activeInstructionId.value === instId ? "hover" : ""
                  }`}
                >
                  <button
                    class="d-flex gap-1 w-100 text-start bg-transparent border-0 p-2"
                    type="button"
                    aria-current={activeInstructionId.value === instId ? "step" : false}
                    onClick={() => selectInstruction(instId)}
                    onFocus={() => focusInstruction(instId)}
                    onPointerEnter={(e) => {
                      if (e.pointerType === "touch") return
                      focusInstruction(instId)
                    }}
                  >
                    <span
                      class={`icon-${inst.iconNum} dark-filter-invert flex-shrink-0`}
                      aria-hidden="true"
                    />
                    <span class="number">{instId + 1}.</span>
                    <span class="instruction flex-grow-1 mx-1">{inst.text}</span>
                    <span class="distance flex-shrink-0">{inst.distanceText}</span>
                  </button>
                </li>
              ))}
            </ol>

            <RoutingAttribution attribution={routeValue.attribution} />
          </>
        )}
      </div>
    </div>
  )
}

export const RoutingRoute = defineRoute({
  id: "routing",
  path: "/directions",
  query: {
    engine: queryParam.string(),
    from: queryParam.string(),
    to: queryParam.string(),
  },
  Component: RoutingSidebar,
})
