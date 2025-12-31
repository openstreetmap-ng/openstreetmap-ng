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
import { qsParse } from "@lib/qs"
import { scrollElementIntoView } from "@lib/scroll"
import { configureStandardForm } from "@lib/standard-form"
import { setPageTitle } from "@lib/title"
import { batch, type Signal, signal, useSignal, useSignalEffect } from "@preact/signals"
import { memoize } from "@std/cache/memoize"
import type { Feature, LineString } from "geojson"
import { t } from "i18next"
import {
  type GeoJSONSource,
  LngLatBounds,
  type LngLatLike,
  type Map as MaplibreMap,
  Marker,
  Point,
  Popup,
} from "maplibre-gl"
import { render } from "preact"
import { useRef } from "preact/hooks"

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

type RouteStepView = {
  iconNum: number
  text: string
  distanceText: string
}

type RouteElevationView = {
  ascendText: string
  descendText: string
}

type RouteView = {
  distanceText: string
  timeText: string
  elevation: RouteElevationView | null
  steps: RouteStepView[]
  attribution: RoutingResult_Attribution
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

const RoutingPopupContent = ({
  stepIndex,
  instruction,
}: {
  stepIndex: number
  instruction: string
}) => (
  <>
    <span class="number">{stepIndex + 1}.</span> <span>{instruction}</span>
  </>
)

const RoutingSidebar = ({
  map,
  active,
  sidebar,
}: {
  map: MaplibreMap
  active: Signal<boolean>
  sidebar: HTMLElement
}) => {
  const loading = useSignal(false)
  const routeView = useSignal<RouteView | null>(null)
  const hoverStepIndex = useSignal<number | null>(null)
  const formRef = useRef<HTMLFormElement>(null)

  // Form State Signals
  const start = useSignal("")
  const startLoaded = useSignal("")
  const startLoadedLon = useSignal("0")
  const startLoadedLat = useSignal("0")

  const end = useSignal("")
  const endLoaded = useSignal("")
  const endLoadedLon = useSignal("0")
  const endLoadedLat = useSignal("0")

  const bbox = useSignal("")

  // Refs for map objects and state that don't need to trigger re-renders
  const markers = useRef<{ start: Marker | null; end: Marker | null }>({
    start: null,
    end: null,
  })
  const startBounds = useRef<LngLatBounds | null>(null)
  const endBounds = useRef<LngLatBounds | null>(null)
  const stepStartCoords = useRef<LngLatLike[]>([])
  const popup = useRef<Popup | null>(null)
  const popupRoot = useRef<HTMLDivElement | null>(null)
  const lastMouse = useRef<[number, number] | null>(null)

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

  const createMarker = (color: MarkerColor, isStart: boolean) => {
    const marker = new Marker({
      anchor: MARKER_ICON_ANCHOR,
      element: getMarkerIconElement(color, true),
      draggable: true,
    })
    marker.on("dragend", () => {
      const lngLat = marker.getLngLat()
      console.debug("Routing: Marker drag end", lngLat, isStart)
      const precision = zoomPrecision(map.getZoom())
      const val = `${lngLat.lat.toFixed(precision)}, ${lngLat.lng.toFixed(precision)}`
      const lonStr = lngLat.lng.toFixed(7)
      const latStr = lngLat.lat.toFixed(7)

      batch(() => {
        if (isStart) {
          start.value = val
          startLoaded.value = val
          startLoadedLon.value = lonStr
          startLoadedLat.value = latStr
        } else {
          end.value = val
          endLoaded.value = val
          endLoadedLon.value = lonStr
          endLoadedLat.value = latStr
        }
      })

      submitFormIfFilled()
    })
    return marker
  }

  const getOrCreateMarker = (dir: "start" | "end") => {
    if (dir === "start") {
      if (!markers.current.start) markers.current.start = createMarker("green", true)
      return markers.current.start
    }
    if (!markers.current.end) markers.current.end = createMarker("red", false)
    return markers.current.end
  }

  const updateHover = (id: number | null, scrollIntoView = false) => {
    const prev = hoverStepIndex.peek()
    if (id === prev) return

    if (prev !== null)
      map.setFeatureState({ source: LAYER_ID, id: prev }, { hover: false })
    hoverStepIndex.value = id

    if (id === null) return

    if (scrollIntoView) {
      const row = sidebar.querySelector(`tr[data-step-index="${id}"]`)
      if (row) scrollElementIntoView(parentSidebar, row)
    }
    map.setFeatureState({ source: LAYER_ID, id }, { hover: true })
  }

  const updateEndpoints = (data: RoutingResult) => {
    const updateEndpoint = (dir: "start" | "end", entry: RoutingResult_Endpoint) => {
      const { minLon, minLat, maxLon, maxLat } = entry.bounds!
      const b = new LngLatBounds([minLon, minLat, maxLon, maxLat])
      if (dir === "start") startBounds.current = b
      else endBounds.current = b

      const name = entry.name
      const lon = entry.lon.toFixed(7)
      const lat = entry.lat.toFixed(7)

      batch(() => {
        if (dir === "start") {
          start.value = name
          startLoaded.value = name
          startLoadedLon.value = lon
          startLoadedLat.value = lat
        } else {
          end.value = name
          endLoaded.value = name
          endLoadedLon.value = lon
          endLoadedLat.value = lat
        }
      })

      getOrCreateMarker(dir).setLngLat([entry.lon, entry.lat]).addTo(map)
    }

    if (data.start) updateEndpoint("start", data.start)
    if (data.end) updateEndpoint("end", data.end)

    const sb = startBounds.current
    const eb = endBounds.current
    const markerBounds = sb && eb ? sb.extend(eb) : (sb ?? eb)
    if (markerBounds) {
      const mapBounds = map.getBounds()
      if (
        !(
          mapBounds.contains(markerBounds.getSouthWest()) ||
          mapBounds.contains(markerBounds.getNorthEast())
        )
      )
        map.fitBounds(markerBounds)
    }
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

    stepStartCoords.current = []
    const steps: RouteStepView[] = []
    let totalDistance = 0
    let totalTime = 0
    let coordsSliceStart = 0

    for (const [stepIndex, step] of route.steps.entries()) {
      totalDistance += step.distance
      totalTime += step.time

      const stepCoords = allCoords.slice(
        coordsSliceStart,
        coordsSliceStart + step.numCoords,
      )
      coordsSliceStart += step.numCoords - 1
      if (step.numCoords > 1) {
        lines.push({
          type: "Feature",
          id: stepIndex,
          properties: {},
          geometry: { type: "LineString", coordinates: stepCoords },
        })
      }

      const startCoord = stepCoords[0] as LngLatLike | undefined
      stepStartCoords.current.push(startCoord ?? allCoords[0])

      steps.push({
        iconNum: step.iconNum,
        text: step.text,
        distanceText: formatDistanceRounded(step.distance),
      })
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
      steps,
      attribution: route.attribution!,
    }

    const source = map.getSource<GeoJSONSource>(LAYER_ID)
    source?.setData({ type: "FeatureCollection", features: lines })
    console.debug("Routing: Loaded", route.steps.length, "steps")
  }

  const updateUrl = () => {
    const { start: mStart, end: mEnd } = markers.current
    if (!(mStart && mEnd)) return

    const precision = zoomPrecision(19)
    const startLngLat = mStart.getLngLat()
    const endLngLat = mEnd.getLngLat()
    const routeParam = `${startLngLat.lat.toFixed(precision)},${startLngLat.lng.toFixed(precision)};${endLngLat.lat.toFixed(precision)},${endLngLat.lng.toFixed(precision)}`

    const url = new URL(window.location.href)
    url.searchParams.set("engine", routingEngineStorage.value)
    url.searchParams.set("route", routeParam)
    window.history.replaceState(null, "", url)
  }

  // --- Handlers ---

  const onInterfaceMarkerDragStart = (e: DragEvent) => {
    const target = e.currentTarget
    if (!(target instanceof HTMLImageElement)) return
    const direction = target.dataset.direction
    if (!direction) return
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
    batch(() => {
      const newStartValue = end.value
      const newEndValue = start.value

      start.value = newStartValue
      end.value = newEndValue

      const { start: mStart, end: mEnd } = markers.current
      if (
        mStart &&
        mEnd &&
        start.value === startLoaded.value &&
        end.value === endLoaded.value
      ) {
        const newStartLngLat = mEnd.getLngLat()
        const newEndLngLat = mStart.getLngLat()

        mStart.setLngLat(newStartLngLat)
        mEnd.setLngLat(newEndLngLat)

        startLoaded.value = newStartValue
        endLoaded.value = newEndValue

        // Swap coordinates as well
        const tempLon = startLoadedLon.value
        startLoadedLon.value = endLoadedLon.value
        endLoadedLon.value = tempLon

        const tempLat = startLoadedLat.value
        startLoadedLat.value = endLoadedLat.value
        endLoadedLat.value = tempLat
      }
    })
    submitFormIfFilled()
  }

  const onStepClick = (stepIndex: number) => {
    const lngLat = stepStartCoords.current[stepIndex]
    if (!lngLat) return
    const route = routeView.value
    const step = route?.steps[stepIndex]
    if (!step) return

    popupRoot.current ??= document.createElement("div")
    popup.current ??= new Popup({
      closeButton: false,
      closeOnClick: false,
      closeOnMove: true,
      anchor: "bottom",
      className: "route-steps",
    })

    render(
      <RoutingPopupContent
        stepIndex={stepIndex}
        instruction={step.text}
      />,
      popupRoot.current,
    )
    popup.current.setDOMContent(popupRoot.current).setLngLat(lngLat).addTo(map)
  }

  const ensureMarkerFromInput = (dir: "start" | "end") => {
    const val = dir === "start" ? start.peek() : end.peek()
    const coords = tryParsePoint(val)
    if (!coords) return
    const [lon, lat] = coords
    getOrCreateMarker(dir).setLngLat([lon, lat]).addTo(map)

    const lonStr = lon.toFixed(7)
    const latStr = lat.toFixed(7)

    batch(() => {
      if (dir === "start") {
        startLoaded.value = val
        startLoadedLon.value = lonStr
        startLoadedLat.value = latStr
      } else {
        endLoaded.value = val
        endLoadedLon.value = lonStr
        endLoadedLat.value = latStr
      }
    })
  }

  // --- Effects ---

  const resetState = () => {
    batch(() => {
      loading.value = false
      routeView.value = null
      hoverStepIndex.value = null
    })
    stepStartCoords.current = []
    markers.current.start?.remove()
    markers.current.start = null
    markers.current.end?.remove()
    markers.current.end = null
    popup.current?.remove()
  }

  const parseUrlParams = (form: HTMLFormElement) => {
    const searchParams = qsParse(window.location.search)

    if (searchParams.route?.includes(";")) {
      const [s, e] = searchParams.route.split(";")
      batch(() => {
        start.value = s
        end.value = e
      })
    }
    if (searchParams.from) start.value = searchParams.from
    if (searchParams.to) end.value = searchParams.to

    ensureMarkerFromInput("start")
    ensureMarkerFromInput("end")

    const routingEngine = searchParams.engine
    if (routingEngine) {
      if (form.querySelector(`select[name=engine] option[value=${routingEngine}]`)) {
        routingEngineStorage.value = routingEngine
      } else {
        console.warn("Routing: Unsupported engine", routingEngine)
      }
    }
  }

  // Effect: Main lifecycle
  useSignalEffect(() => {
    if (!active.value) {
      resetState()
      removeMapLayer(map, LAYER_ID)
      clearMapHover(map, LAYER_ID)
      return
    }

    switchActionSidebar(map, sidebar)
    setPageTitle(t("javascripts.directions.directions"))
    addMapLayer(map, LAYER_ID)

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
          batch(() => {
            updateHover(null)
            routeView.value = null
            loading.value = true
          })

          formData.set("start_loaded", startLoaded.peek())
          formData.set("start_loaded_lon", startLoadedLon.peek())
          formData.set("start_loaded_lat", startLoadedLat.peek())
          formData.set("end_loaded", endLoaded.peek())
          formData.set("end_loaded_lon", endLoadedLon.peek())
          formData.set("end_loaded_lat", endLoadedLat.peek())
          formData.set("bbox", bbox.peek())
          return null
        },
        errorCallback: () => {
          if (!active.value) return
          loading.value = false
        },
      },
    )

    // Bbox tracking
    const onMapZoomOrMoveEnd = () => {
      const [[minLon, minLat], [maxLon, maxLat]] = map
        .getBounds()
        .adjustAntiMeridian()
        .toArray()
      bbox.value = `${minLon},${minLat},${maxLon},${maxLat}`
    }
    onMapZoomOrMoveEnd()

    parseUrlParams(formRef.current!)
    submitFormIfFilled()

    // Event listeners
    const onMapClick = (e: any) => {
      const features = map.queryRenderedFeatures(e.point, { layers: [LAYER_ID] })
      const feature = features[0] as Feature<LineString> | undefined
      if (feature) {
        const featureId = feature.id as number
        if (featureId >= 0) onStepClick(featureId)
      } else {
        popup.current?.remove()
      }
    }

    const onMapMouseMove = (e: any) => {
      const id = e.features?.[0].id as number
      setMapHover(map, LAYER_ID)
      updateHover(id >= 0 ? id : null, true)
    }
    const onMapMouseLeave = () => {
      clearMapHover(map, LAYER_ID)
      updateHover(null)
    }
    const onMapDragOver = (e: DragEvent) => e.preventDefault()
    const onMapDrop = (e: DragEvent) => {
      const dragData = e.dataTransfer?.getData(DRAG_DATA_TYPE)
      if (dragData !== "start" && dragData !== "end") return
      const mapContainer = map.getContainer()
      const mapRect = mapContainer.getBoundingClientRect()
      const mousePoint = new Point(e.clientX - mapRect.left, e.clientY - mapRect.top)
      getOrCreateMarker(dragData)
        .setLngLat(map.unproject(mousePoint))
        .addTo(map)
        .fire("dragend")
    }
    const onSidebarMouseMove = (e: MouseEvent) => {
      lastMouse.current = [e.clientX, e.clientY]
    }
    const onSidebarScroll = () => {
      if (!lastMouse.current) return
      const [x, y] = lastMouse.current
      const r = parentSidebar.getBoundingClientRect()
      if (x < r.left || x > r.right || y < r.top || y > r.bottom) return
      const row = document.elementFromPoint(x, y)?.closest("tr[data-step-index]")
      const stepIndex = row instanceof HTMLElement ? row.dataset.stepIndex : undefined
      updateHover(stepIndex ? Number.parseInt(stepIndex, 10) : null)
    }

    map.on("moveend", onMapZoomOrMoveEnd)
    map.on("click", onMapClick)
    map.on("mousemove", LAYER_ID, onMapMouseMove)
    map.on("mouseleave", LAYER_ID, onMapMouseLeave)
    const mapContainer = map.getContainer()
    mapContainer.addEventListener("dragover", onMapDragOver)
    mapContainer.addEventListener("drop", onMapDrop)
    parentSidebar.addEventListener("mousemove", onSidebarMouseMove)
    parentSidebar.addEventListener("scroll", onSidebarScroll)

    return () => {
      disposeForm?.()
      map.off("moveend", onMapZoomOrMoveEnd)
      map.off("click", onMapClick)
      map.off("mousemove", LAYER_ID, onMapMouseMove)
      map.off("mouseleave", LAYER_ID, onMapMouseLeave)
      mapContainer.removeEventListener("dragover", onMapDragOver)
      mapContainer.removeEventListener("drop", onMapDrop)
      parentSidebar.removeEventListener("mousemove", onSidebarMouseMove)
      parentSidebar.removeEventListener("scroll", onSidebarScroll)
    }
  })

  const routeValue = routeView.value
  const hoverValue = hoverStepIndex.value

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
            <label>{t("site.search.from")}</label>
            <input
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
            loading="lazy"
            draggable
            data-direction="start"
            title={t("map.routing.drag_and_drop.start")}
            onDragStart={onInterfaceMarkerDragStart}
          />
        </div>

        <div class="d-flex align-items-end mb-1">
          <div class="custom-input-group flex-grow-1 me-2">
            <label>{t("site.search.to")}</label>
            <input
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
            loading="lazy"
            draggable
            data-direction="end"
            title={t("map.routing.drag_and_drop.end")}
            onDragStart={onInterfaceMarkerDragStart}
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
            <label class="form-label">{t("map.routing.engine.title")}</label>
            <select
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
                  <i class="bi bi-signpost-2" />
                  <span class="mx-1">{t("javascripts.directions.distance")}:</span>
                  <span>{routeValue.distanceText}</span>
                </span>
                <span>
                  <i class="bi bi-stopwatch" />
                  <span class="mx-1">{t("javascripts.directions.time")}:</span>
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
                {routeValue.steps.map((step, stepIndex) => (
                  <tr
                    data-step-index={stepIndex.toString()}
                    class={hoverValue === stepIndex ? "hover" : ""}
                    onClick={() => onStepClick(stepIndex)}
                    onMouseEnter={() => updateHover(stepIndex)}
                    onMouseLeave={() => updateHover(null)}
                    key={stepIndex}
                  >
                    <td class="icon">
                      <div class={`icon-${step.iconNum} dark-filter-invert`} />
                    </td>
                    <td class="number">{stepIndex + 1}.</td>
                    <td>{step.text}</td>
                    <td class="distance">{step.distanceText}</td>
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
  const sidebar = getActionSidebar("routing")
  const active = signal(false)

  render(
    <RoutingSidebar
      map={map}
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
