import {
  getActionSidebar,
  SidebarHeader,
  switchActionSidebar,
} from "@index/_action-sidebar"
import { tryParsePoint, zoomPrecision } from "@lib/coords"
import {
  formatDistance,
  formatDistanceRounded,
  formatHeight,
  formatTime,
} from "@lib/format"
import { tRich } from "@lib/i18n"
import { routingEngineStorage } from "@lib/local-storage"
import { boundsToString, boundsUnion, fitBoundsIfNeeded } from "@lib/map/bounds"
import { clearMapHover, setMapHover } from "@lib/map/hover"
import {
  addMapLayer,
  emptyFeatureCollection,
  type LayerId,
  layersConfig,
  removeMapLayer,
} from "@lib/map/layers/layers"
import {
  getMarkerIconElement,
  MARKER_ICON_ANCHOR,
  type MarkerColor,
} from "@lib/map/marker"
import { decodeLonLat } from "@lib/polyline"
import {
  type RoutingResult,
  type RoutingResult_Attribution,
  type RoutingResult_Endpoint,
  RoutingResultSchema,
} from "@lib/proto/shared_pb"
import { qsParse, updateSearchParams } from "@lib/qs"
import { scrollElementIntoView } from "@lib/scroll"
import { configureStandardForm } from "@lib/standard-form"
import { setPageTitle } from "@lib/title"
import type { Bounds } from "@lib/types"
import {
  type ReadonlySignal,
  signal,
  useSignal,
  useSignalEffect,
} from "@preact/signals"
import { memoize } from "@std/cache/memoize"
import type { Feature, LineString } from "geojson"
import { t } from "i18next"
import {
  type GeoJSONSource,
  type LngLat,
  LngLatBounds,
  type Map as MaplibreMap,
  Marker,
  Point,
  Popup,
} from "maplibre-gl"
import { render } from "preact"
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
  ["graphhopper_bicycle", t("javascripts.directions.engines.graphhopper_bicycle")],
  ["osrm_bike", t("javascripts.directions.engines.fossgis_osrm_bike")],
  ["valhalla_bicycle", t("javascripts.directions.engines.fossgis_valhalla_bicycle")],
  ["graphhopper_foot", t("javascripts.directions.engines.graphhopper_foot")],
  ["osrm_foot", t("javascripts.directions.engines.fossgis_osrm_foot")],
  ["valhalla_pedestrian", t("javascripts.directions.engines.fossgis_valhalla_foot")],
])

type RouteSegmentView = {
  id: number
  iconNum: number
  text: string
  distanceText: string
  end: [number, number]
  bounds: LngLatBounds
}

type RouteElevationView = {
  ascendText: string
  descendText: string
}

type RouteView = {
  distanceText: string
  timeText: string
  elevation: RouteElevationView | null
  segments: RouteSegmentView[]
  attribution: RoutingResult_Attribution
}

type LoadedEndpoint = {
  value: string
  lon: string
  lat: string
}

const findSegmentId = (features: Array<{ id?: unknown }> | undefined) => {
  if (!features) return null
  for (const feature of features) {
    const { id } = feature
    if (typeof id === "number" && id >= 0) return id
  }
  return null
}

const RoutingAttribution = ({
  attribution,
}: {
  attribution: RoutingResult_Attribution
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
  mapContainer,
  source,
  active,
  sidebar,
}: {
  map: MaplibreMap
  mapContainer: HTMLElement
  source: GeoJSONSource
  active: ReadonlySignal<boolean>
  sidebar: HTMLElement
}) => {
  const loading = useSignal(false)
  const routeView = useSignal<RouteView | null>(null)
  const hoverSegmentId = useSignal<number | null>(null)
  const formRef = useRef<HTMLFormElement>(null)
  const engineInputId = useId()

  // Form State Signals
  const startInputId = useId()
  const start = useSignal("")
  const startLoaded = useRef<LoadedEndpoint>({ value: "", lon: "0", lat: "0" })

  const endInputId = useId()
  const end = useSignal("")
  const endLoaded = useRef<LoadedEndpoint>({ value: "", lon: "0", lat: "0" })

  const markers = useRef<{ start: Marker | null; end: Marker | null }>({
    start: null,
    end: null,
  })
  const popup = useRef<Popup | null>(null)
  const popupContent = useRef<{
    root: HTMLDivElement
    number: HTMLSpanElement
    instruction: HTMLSpanElement
  } | null>(null)
  const lastMouse = useRef<[number, number] | null>(null)
  const sidebarHovered = useRef(false)

  const parentSidebar = sidebar.closest("div.sidebar")!

  const submitFormIfFilled = () => {
    popup.current?.remove()
    if (!(start.peek() && end.peek())) return

    const form = formRef.current!
    ;(form.elements.namedItem("start") as HTMLInputElement).value = start.peek()
    ;(form.elements.namedItem("end") as HTMLInputElement).value = end.peek()
    form.requestSubmit()
  }

  // --- Map & Interaction Logic ---

  const setLoadedEndpoint = (
    dir: "start" | "end",
    value: string,
    lon: number,
    lat: number,
  ) => {
    const endpoint = dir === "start" ? startLoaded.current : endLoaded.current
    endpoint.value = value
    endpoint.lon = lon.toFixed(7)
    endpoint.lat = lat.toFixed(7)
  }

  const setEndpointFromLngLat = (
    dir: "start" | "end",
    lngLat: LngLat,
    value: string,
  ) => {
    setLoadedEndpoint(dir, value, lngLat.lng, lngLat.lat)
    if (dir === "start") start.value = value
    else end.value = value
  }

  const createMarker = (color: MarkerColor, dir: "start" | "end") => {
    const marker = new Marker({
      anchor: MARKER_ICON_ANCHOR,
      element: getMarkerIconElement(color, true),
      draggable: true,
    })
    marker.on("dragend", () => {
      const lngLat = marker.getLngLat()
      console.debug("Routing: Marker drag end", lngLat, dir)
      const precision = zoomPrecision(map.getZoom())
      const val = `${lngLat.lat.toFixed(precision)}, ${lngLat.lng.toFixed(precision)}`
      setEndpointFromLngLat(dir, lngLat, val)

      submitFormIfFilled()
    })
    return marker
  }

  const getOrCreateMarker = (dir: "start" | "end") => {
    if (dir === "start") {
      if (!markers.current.start) markers.current.start = createMarker("green", "start")
      return markers.current.start
    }
    if (!markers.current.end) markers.current.end = createMarker("red", "end")
    return markers.current.end
  }

  const updateHover = (segmentId: number | null, scrollIntoView = false) => {
    const prev = hoverSegmentId.peek()
    if (segmentId === prev) return

    if (prev !== null)
      map.setFeatureState({ source: LAYER_ID, id: prev }, { hover: false })
    hoverSegmentId.value = segmentId

    if (segmentId === null) return

    if (scrollIntoView) {
      const row = sidebar.querySelector(`tr[data-segment-id="${segmentId}"]`)
      if (row) scrollElementIntoView(parentSidebar, row)
    }
    map.setFeatureState({ source: LAYER_ID, id: segmentId }, { hover: true })
  }

  const updateEndpoints = (data: RoutingResult) => {
    let markerBounds: Bounds | null = null

    const updateEndpoint = (dir: "start" | "end", entry: RoutingResult_Endpoint) => {
      const { minLon, minLat, maxLon, maxLat } = entry.bounds!
      markerBounds = boundsUnion(markerBounds, [minLon, minLat, maxLon, maxLat])

      setLoadedEndpoint(dir, entry.name, entry.lon, entry.lat)
      if (dir === "start") start.value = entry.name
      else end.value = entry.name

      getOrCreateMarker(dir).setLngLat([entry.lon, entry.lat]).addTo(map)
    }

    if (data.start) updateEndpoint("start", data.start)
    if (data.end) updateEndpoint("end", data.end)
    if (markerBounds)
      fitBoundsIfNeeded(map, markerBounds, {
        animate: true,
      })
  }

  const updateRoute = (route: RoutingResult) => {
    const lines: Feature<LineString>[] = []
    const allCoords = decodeLonLat(route.line, route.lineQuality)

    if (allCoords.length) {
      lines.push({
        type: "Feature",
        id: -1,
        properties: { base: true },
        geometry: { type: "LineString", coordinates: allCoords },
      })
    }

    const segments: RouteSegmentView[] = []
    let totalDistance = 0
    let totalTime = 0
    let coordsSliceStart = 0

    const lastStep = route.steps.at(-1)!
    const endManeuverByStepIndex = new Array<RoutingResult["steps"][number]>(
      route.steps.length,
    )
    let nextNonEmptyManeuver = lastStep
    for (let i = route.steps.length - 1; i >= 0; i--) {
      endManeuverByStepIndex[i] = nextNonEmptyManeuver
      const step = route.steps[i]!
      if (step.text) nextNonEmptyManeuver = step
    }

    for (const [stepIndex, step] of route.steps.entries()) {
      totalDistance += step.distance
      totalTime += step.time

      const stepCoords = allCoords.slice(
        coordsSliceStart,
        coordsSliceStart + step.numCoords,
      )
      if (step.numCoords) {
        coordsSliceStart += step.numCoords - 1
      }

      if (stepCoords.length > 1) {
        const end = stepCoords[stepCoords.length - 1]!
        const bounds = stepCoords.reduce(
          (bounds, coord) => bounds.extend(coord),
          new LngLatBounds(),
        )

        const maneuverStep = endManeuverByStepIndex[stepIndex]!
        const segment: RouteSegmentView = {
          id: stepIndex,
          iconNum: maneuverStep.iconNum,
          text: maneuverStep.text,
          distanceText: formatDistanceRounded(step.distance),
          end,
          bounds,
        }
        segments.push(segment)

        lines.push({
          type: "Feature",
          id: stepIndex,
          properties: {},
          geometry: { type: "LineString", coordinates: stepCoords },
        })
      }
    }

    routeView.value = {
      distanceText: formatDistance(totalDistance),
      timeText: formatTime(totalTime),
      elevation: route.elevation
        ? {
            ascendText: formatHeight(route.elevation.ascend),
            descendText: formatHeight(route.elevation.descend),
          }
        : null,
      segments,
      attribution: route.attribution!,
    }

    source.setData({ type: "FeatureCollection", features: lines })
    console.debug("Routing: Loaded", route.steps.length, "steps")
  }

  const updateUrl = () => {
    const { start: mStart, end: mEnd } = markers.current
    if (!(mStart && mEnd)) return

    const precision = zoomPrecision(19)
    const startLngLat = mStart.getLngLat()
    const endLngLat = mEnd.getLngLat()
    const routeParam = `${startLngLat.lat.toFixed(precision)},${startLngLat.lng.toFixed(precision)};${endLngLat.lat.toFixed(precision)},${endLngLat.lng.toFixed(precision)}`

    updateSearchParams((searchParams) => {
      searchParams.set("engine", routingEngineStorage.value)
      searchParams.set("route", routeParam)
    })
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

  const onInterfaceMarkerDragStart = (direction: "start" | "end") => (e: DragEvent) => {
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
    const shouldSwapLoaded =
      start.peek() === startLoaded.current.value &&
      end.peek() === endLoaded.current.value

    const newStartValue = end.peek()
    const newEndValue = start.peek()
    start.value = newStartValue
    end.value = newEndValue

    const { start: mStart, end: mEnd } = markers.current
    if (shouldSwapLoaded && mStart && mEnd) {
      const newStartLngLat = mEnd.getLngLat()
      const newEndLngLat = mStart.getLngLat()

      mStart.setLngLat(newStartLngLat)
      mEnd.setLngLat(newEndLngLat)

      const startLoadedTemp = startLoaded.current
      startLoaded.current = endLoaded.current
      endLoaded.current = startLoadedTemp
    }
    submitFormIfFilled()
  }

  const handleSegmentClick = (segmentId: number, focus = false) => {
    const route = routeView.value
    if (!route) return
    const segmentIndex = route.segments.findIndex((s) => s.id === segmentId)
    if (segmentIndex === -1) return
    const segment = route.segments[segmentIndex]!

    if (focus)
      fitBoundsIfNeeded(map, segment.bounds, {
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

    const { root, number, instruction } = getOrCreatePopupContent()
    number.textContent = `${segmentIndex + 1}.`
    instruction.textContent = segment.text
    popup.current.setDOMContent(root).setLngLat(segment.end).addTo(map)
  }

  const ensureMarkerFromInput = (dir: "start" | "end") => {
    const val = dir === "start" ? start.peek() : end.peek()
    const coords = tryParsePoint(val)
    if (!coords) return
    const [lon, lat] = coords
    getOrCreateMarker(dir).setLngLat([lon, lat]).addTo(map)
    setLoadedEndpoint(dir, val, lon, lat)
  }

  // --- Effects ---

  const resetState = () => {
    loading.value = false
    routeView.value = null
    hoverSegmentId.value = null
    sidebarHovered.current = false
    lastMouse.current = null
    markers.current.start?.remove()
    markers.current.start = null
    markers.current.end?.remove()
    markers.current.end = null
    popup.current?.remove()
  }

  const parseUrlParams = () => {
    const searchParams = qsParse(window.location.search)

    if (searchParams.route?.includes(";")) {
      const [s, e] = searchParams.route.split(";")
      start.value = s
      end.value = e
    }
    if (searchParams.from) start.value = searchParams.from
    if (searchParams.to) end.value = searchParams.to

    ensureMarkerFromInput("start")
    ensureMarkerFromInput("end")

    const routingEngine = searchParams.engine
    if (routingEngine) {
      if (ROUTING_ENGINES().some(([value]) => value === routingEngine)) {
        routingEngineStorage.value = routingEngine
      } else {
        console.warn("Routing: Unsupported engine", routingEngine)
      }
    }
  }

  // Effect: Main lifecycle
  useSignalEffect(() => {
    if (!active.value) return

    switchActionSidebar(map, sidebar)
    setPageTitle(t("javascripts.directions.directions"))
    addMapLayer(map, LAYER_ID)

    const disposers: Array<() => void> = []
    const onMap = (event: string, handler: any) => {
      map.on(event as any, handler)
      disposers.push(() => map.off(event as any, handler))
    }
    const onMapLayer = (event: string, layerId: string, handler: any) => {
      map.on(event as any, layerId, handler)
      disposers.push(() => map.off(event as any, layerId, handler))
    }
    const onDom = (target: EventTarget, event: string, handler: any) => {
      target.addEventListener(event, handler)
      disposers.push(() => target.removeEventListener(event, handler))
    }

    // Form configuration
    const disposeForm = configureStandardForm<RoutingResult>(
      formRef.current,
      (data) => {
        if (!active.value) return
        loading.value = false
        console.debug("Routing: Route calculated", data)
        updateEndpoints(data)
        updateUrl()
        updateRoute(data)
      },
      {
        abortSignal: true,
        protobuf: RoutingResultSchema,
        validationCallback: (formData) => {
          if (!active.value) return null
          popup.current?.remove()
          updateHover(null)
          routeView.value = null
          loading.value = true

          formData.set("start_loaded", startLoaded.current.value)
          formData.set("start_loaded_lon", startLoaded.current.lon)
          formData.set("start_loaded_lat", startLoaded.current.lat)
          formData.set("end_loaded", endLoaded.current.value)
          formData.set("end_loaded_lon", endLoaded.current.lon)
          formData.set("end_loaded_lat", endLoaded.current.lat)
          formData.set("bbox", boundsToString(map.getBounds()))
          return null
        },
        errorCallback: () => {
          if (!active.value) return
          loading.value = false
        },
      },
    )
    if (disposeForm) disposers.push(disposeForm)

    parseUrlParams()
    submitFormIfFilled()

    // Event listeners
    const onMapClick = (e: any) => {
      const segmentId = findSegmentId(
        map.queryRenderedFeatures(e.point, { layers: [LAYER_ID] }),
      )
      if (segmentId !== null) {
        handleSegmentClick(segmentId)
      } else {
        popup.current?.remove()
      }
    }

    const onMapMouseMove = (e: any) => {
      const segmentId = findSegmentId(e.features)
      setMapHover(map, LAYER_ID)
      updateHover(segmentId, true)
    }
    const onMapMouseLeave = () => {
      clearMapHover(map, LAYER_ID)
      updateHover(null)
    }
    const onMapDragOver = (e: DragEvent) => e.preventDefault()
    const onMapDrop = (e: DragEvent) => {
      const dragData = e.dataTransfer?.getData(DRAG_DATA_TYPE)
      if (dragData !== "start" && dragData !== "end") return
      const mapRect = mapContainer.getBoundingClientRect()
      const mousePoint = new Point(e.clientX - mapRect.left, e.clientY - mapRect.top)
      getOrCreateMarker(dragData)
        .setLngLat(map.unproject(mousePoint))
        .addTo(map)
        .fire("dragend")
    }
    const onSidebarMouseEnter = () => {
      sidebarHovered.current = true
    }
    const onSidebarMouseLeave = () => {
      sidebarHovered.current = false
      lastMouse.current = null
    }
    const onSidebarMouseMove = (e: MouseEvent) => {
      lastMouse.current = [e.clientX, e.clientY]
    }
    const onSidebarScroll = () => {
      if (!(sidebarHovered.current && lastMouse.current)) return
      const [x, y] = lastMouse.current
      const r = parentSidebar.getBoundingClientRect()
      if (x < r.left || x > r.right || y < r.top || y > r.bottom) return
      const row = document.elementFromPoint(x, y)?.closest("tr[data-segment-id]")
      updateHover(
        row instanceof HTMLElement ? Number.parseInt(row.dataset.segmentId!, 10) : null,
      )
    }

    onMap("click", onMapClick)
    onMapLayer("mousemove", LAYER_ID, onMapMouseMove)
    onMapLayer("mouseleave", LAYER_ID, onMapMouseLeave)
    onDom(mapContainer, "dragover", onMapDragOver)
    onDom(mapContainer, "drop", onMapDrop)
    onDom(parentSidebar, "mouseenter", onSidebarMouseEnter)
    onDom(parentSidebar, "mouseleave", onSidebarMouseLeave)
    onDom(parentSidebar, "mousemove", onSidebarMouseMove)
    onDom(parentSidebar, "scroll", onSidebarScroll)

    return () => {
      for (const dispose of disposers.reverse()) dispose()

      resetState()
      removeMapLayer(map, LAYER_ID)
      clearMapHover(map, LAYER_ID)
    }
  })

  const routeValue = routeView.value
  const hoverValue = hoverSegmentId.value

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
              name="start"
              required
              value={start}
              onInput={(e) => (start.value = e.currentTarget.value)}
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
              name="end"
              required
              value={end}
              onInput={(e) => (end.value = e.currentTarget.value)}
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
              name="engine"
              required
              value={routingEngineStorage}
              onInput={(e) => {
                routingEngineStorage.value = e.currentTarget.value
                submitFormIfFilled()
              }}
            >
              {ROUTING_ENGINES().map(([value, label]) => (
                <option
                  value={value}
                  key={value}
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

            <table class="route-steps table table-sm align-middle mb-4">
              <tbody>
                {routeValue.segments.map((segment, segmentIndex) => (
                  <tr
                    data-segment-id={segment.id.toString()}
                    class={hoverValue === segment.id ? "hover" : ""}
                    onClick={() => handleSegmentClick(segment.id, true)}
                    onMouseEnter={() => updateHover(segment.id)}
                    onMouseLeave={() => updateHover(null)}
                    key={segment.id}
                  >
                    <td class="icon">
                      <div class={`icon-${segment.iconNum} dark-filter-invert`} />
                    </td>
                    <td class="number">{segmentIndex + 1}.</td>
                    <td class="instruction">{segment.text}</td>
                    <td class="distance">{segment.distanceText}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <RoutingAttribution attribution={routeValue.attribution} />
          </>
        )}
      </div>
    </div>
  )
}

export const getRoutingController = (map: MaplibreMap) => {
  const mapContainer = map.getContainer()
  const source = map.getSource<GeoJSONSource>(LAYER_ID)!
  const sidebar = getActionSidebar("routing")
  const active = signal(false)

  render(
    <RoutingSidebar
      map={map}
      mapContainer={mapContainer}
      source={source}
      active={active}
      sidebar={sidebar}
    />,
    sidebar,
  )

  return {
    load: () => {
      active.value = true
    },
    unload: () => {
      active.value = false
    },
  }
}
