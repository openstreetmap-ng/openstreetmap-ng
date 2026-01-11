import {
  getActionSidebar,
  SidebarHeader,
  switchActionSidebar,
} from "@index/_action-sidebar"
import { formatDistance, isMetricUnit } from "@lib/format"
import { fitBoundsIfNeeded } from "@lib/map/bounds"
import { closestPointOnSegment } from "@lib/map/geometry"
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
import { decodeLonLat, encodeLonLat } from "@lib/polyline"
import { getSearchParam, updateSearchParams } from "@lib/qs"
import { setPageTitle } from "@lib/title"
import {
  batch,
  type ReadonlySignal,
  signal,
  useComputed,
  useSignal,
  useSignalEffect,
} from "@preact/signals"
import { throttle } from "@std/async/unstable-throttle"
import type { Feature, LineString } from "geojson"
import { t } from "i18next"
import {
  type GeoJSONFeatureDiff,
  type GeoJSONSource,
  LngLat,
  LngLatBounds,
  type LngLatLike,
  type Map as MaplibreMap,
  MapMouseEvent,
  Marker,
  Point,
} from "maplibre-gl"
import { render } from "preact"
import { useRef } from "preact/hooks"

type DistanceUnit = "metric" | "imperial"

type MarkerEntry = {
  id: number
  index: number
  marker: Marker
}

interface DistanceLabel extends Marker {
  distance: number
}

const LAYER_ID = "distance" as LayerId
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
      "line-color": "#6ea8fe",
      "line-width": 5,
    },
  },
  priority: 160,
})

const DistanceSidebar = ({
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
  const unit = useSignal<DistanceUnit>(isMetricUnit() ? "metric" : "imperial")
  const markersCount = useSignal(0)
  const totalDistance = useSignal(0)

  const nextMarkerId = useRef(0)
  const positions = useRef<[number, number][]>([])
  const labels = useRef<Map<string, DistanceLabel>>(new Map())
  const markers = useRef<MarkerEntry[]>([])
  const ghostMarker = useRef<Marker | null>(null)
  const ghostMarkerIndex = useRef(-1)
  const dragMode = useRef<"none" | "marker" | "ghost">("none")

  const totalDistanceText = useComputed(() =>
    formatDistance(totalDistance.value, unit.value),
  )

  const throttledUpdateHistory = throttle(
    () => {
      // Allow state mutations during unload without touching the URL after navigation.
      if (!active.value) return

      updateSearchParams((searchParams) => {
        if (positions.current.length) {
          searchParams.set("line", encodeLonLat(positions.current, 5))
        } else {
          searchParams.delete("line")
        }
      })
    },
    500,
    { ensureLastCall: true },
  )

  const setMarkerIcon = (marker: Marker, color: MarkerColor) => {
    marker.getElement().replaceChildren(...getMarkerIconElement(color, true).children)
  }

  const refreshEndpointColors = () => {
    const count = markers.current.length
    if (!count) return

    setMarkerIcon(markers.current[0].marker, "green")
    if (count === 1) return
    setMarkerIcon(markers.current[count - 1].marker, "red")
  }

  const commitMarkersChange = (updateUrl = true) => {
    refreshEndpointColors()
    markersCount.value = markers.current.length
    if (updateUrl) throttledUpdateHistory()
  }

  const getOrCreateLabel = (segmentId: string) => {
    const existing = labels.current.get(segmentId)
    if (existing) return existing

    const label = new Marker({
      anchor: "center",
      element: document.createElement("div"),
      className: "distance-label",
    })
      .setLngLat([0, 0])
      .addTo(map) as DistanceLabel
    label.distance = 0
    labels.current.set(segmentId, label)
    return label
  }

  const removeLabel = (segmentId: string) => {
    const label = labels.current.get(segmentId)
    if (!label) return
    totalDistance.value = totalDistance.peek() - label.distance
    label.remove()
    labels.current.delete(segmentId)
  }

  const updateLabel = (segmentId: string, startIndex: number, endIndex: number) => {
    const label = getOrCreateLabel(segmentId)
    const startCoord = positions.current[startIndex]
    const endCoord = positions.current[endIndex]

    const startScreenPoint = map.project(startCoord)
    const endScreenPoint = map.project(endCoord)

    // Calculate middle point
    // TODO: make sure this works correctly with 3d globe (#155)
    const middlePoint = map.unproject(
      new Point(
        (startScreenPoint.x + endScreenPoint.x) / 2, //
        (startScreenPoint.y + endScreenPoint.y) / 2,
      ),
    )

    let angle = Math.atan2(
      endScreenPoint.y - startScreenPoint.y,
      endScreenPoint.x - startScreenPoint.x,
    )
    if (angle > Math.PI / 2) angle -= Math.PI
    if (angle < -Math.PI / 2) angle += Math.PI

    const newDistance = new LngLat(startCoord[0], startCoord[1]).distanceTo(
      new LngLat(endCoord[0], endCoord[1]),
    )

    totalDistance.value = totalDistance.peek() + (newDistance - label.distance)
    label.distance = newDistance
    label.setLngLat(middlePoint)
    label.setRotation((angle * 180) / Math.PI)
    label.getElement().textContent = formatDistance(newDistance, unit.peek())
  }

  const segmentIdAt = (endIndex: number) =>
    `${markers.current[endIndex - 1].id}:${markers.current[endIndex].id}`

  const makeSegmentFeatureAt = (endIndex: number): Feature<LineString> => ({
    type: "Feature",
    id: segmentIdAt(endIndex),
    properties: {},
    geometry: {
      type: "LineString",
      coordinates: [positions.current[endIndex - 1], positions.current[endIndex]],
    },
  })

  const makeSegmentUpdateAt = (endIndex: number): GeoJSONFeatureDiff => ({
    id: segmentIdAt(endIndex),
    newGeometry: {
      type: "LineString",
      coordinates: [positions.current[endIndex - 1], positions.current[endIndex]],
    },
  })

  const updateLabelAt = (endIndex: number) => {
    updateLabel(segmentIdAt(endIndex), endIndex - 1, endIndex)
  }

  const updateSegmentsAt = (endIndexes: readonly number[]) => {
    if (!endIndexes.length) return

    source.updateData({
      update: endIndexes.map(makeSegmentUpdateAt),
    })
    for (const endIndex of endIndexes) updateLabelAt(endIndex)
  }

  const updateSegmentsAround = (markerIndex: number) => {
    const count = markers.current.length
    if (count < 2) return

    const segments: number[] = []
    if (markerIndex > 0) segments.push(markerIndex)
    if (markerIndex < count - 1) segments.push(markerIndex + 1)
    updateSegmentsAt(segments)
  }

  const rebuildSegmentsAndLabels = () => {
    totalDistance.value = 0
    for (const label of labels.current.values()) label.remove()
    labels.current.clear()

    if (markers.current.length < 2) {
      source.updateData({ removeAll: true })
      return
    }

    const segmentEndIndexes: number[] = []
    for (let endIndex = 1; endIndex < markers.current.length; endIndex++) {
      segmentEndIndexes.push(endIndex)
    }

    source.updateData({
      removeAll: true,
      add: segmentEndIndexes.map(makeSegmentFeatureAt),
    })

    for (const endIndex of segmentEndIndexes) updateLabelAt(endIndex)
  }

  const clearMarkers = () => {
    if (markers.current.length) console.debug("Distance: Clear markers")
    resetState()
    throttledUpdateHistory()
  }

  const toggleUnit = () => {
    unit.value = unit.value === "metric" ? "imperial" : "metric"
    console.debug("Distance: Unit toggled", unit.value)

    for (const label of labels.current.values()) {
      label.getElement().textContent = formatDistance(label.distance, unit.value)
    }
  }

  const removeMarker = (index: number) => {
    console.debug("Distance: Marker removed", index)
    if (!active.peek()) return

    const target = markers.current[index]
    const countBefore = markers.current.length

    const toRemove: string[] = []
    if (index > 0) toRemove.push(segmentIdAt(index))
    if (index < countBefore - 1) toRemove.push(segmentIdAt(index + 1))

    target.marker.remove()
    markers.current.splice(index, 1)
    positions.current.splice(index, 1)
    for (let i = index; i < markers.current.length; i++) markers.current[i].index = i

    const bridgeSegmentEndIndex = index
    const shouldAddBridge =
      bridgeSegmentEndIndex > 0 && bridgeSegmentEndIndex < markers.current.length

    if (toRemove.length || shouldAddBridge) {
      const diff = {} as Parameters<GeoJSONSource["updateData"]>[0]
      if (toRemove.length) diff.remove = toRemove
      if (shouldAddBridge) diff.add = [makeSegmentFeatureAt(bridgeSegmentEndIndex)]
      source.updateData(diff)
    }

    for (const id of toRemove) removeLabel(id)

    if (shouldAddBridge) updateLabelAt(bridgeSegmentEndIndex)

    commitMarkersChange()
  }

  const markerFactory = (color: MarkerColor) => {
    return new Marker({
      anchor: MARKER_ICON_ANCHOR,
      element: getMarkerIconElement(color, true),
      className: "distance-marker",
      draggable: true,
    })
  }

  const updateMarkerDataAt = (index: number, lngLat: LngLat) => {
    if (!active.peek()) return
    positions.current[index] = [lngLat.lng, lngLat.lat]
    updateSegmentsAround(index)
    throttledUpdateHistory()
  }

  const createMarkerEntry = (lngLat: LngLatLike, index: number, color: MarkerColor) => {
    const id = nextMarkerId.current++
    const marker = markerFactory(color).setLngLat(lngLat).addTo(map)

    const entry: MarkerEntry = { id, index, marker }

    marker.on("dragstart", () => {
      dragMode.current = "marker"
      hideGhostMarker()
    })
    marker.on(
      "drag",
      throttle(
        () => {
          updateMarkerDataAt(index, marker.getLngLat())
        },
        16,
        { ensureLastCall: true },
      ),
    )
    marker.on("dragend", () => {
      dragMode.current = "none"
    })
    marker.getElement().addEventListener("click", (e) => {
      e.stopPropagation()
      batch(() => {
        removeMarker(index)
      })
    })

    const normalized = LngLat.convert(lngLat)
    positions.current.splice(index, 0, [normalized.lng, normalized.lat])
    markers.current.splice(index, 0, entry)
    for (let i = index; i < markers.current.length; i++) markers.current[i].index = i

    return entry
  }

  const addMarkerAtEnd = (lngLat: LngLatLike, skipUpdates = false) => {
    if (!active.peek()) return
    const prevCount = markers.current.length
    console.debug("Distance: Marker created", lngLat, skipUpdates)

    if (prevCount >= 2) setMarkerIcon(markers.current[prevCount - 1].marker, "blue")
    const color: MarkerColor = prevCount === 0 ? "green" : "red"

    createMarkerEntry(lngLat, prevCount, color)

    if (skipUpdates) return

    if (prevCount > 0) {
      const segmentEndIndex = prevCount
      source.updateData({ add: [makeSegmentFeatureAt(segmentEndIndex)] })
      updateLabelAt(segmentEndIndex)
    }

    commitMarkersChange()
  }

  const insertMarkerAt = (index: number, lngLat: LngLat) => {
    if (!active.peek()) return
    console.debug("Distance: Marker inserted", index, lngLat.lng, lngLat.lat)

    if (index <= 0 || index >= markers.current.length) {
      addMarkerAtEnd(lngLat)
      return
    }

    const oldSegmentId = segmentIdAt(index)

    removeLabel(oldSegmentId)

    createMarkerEntry(lngLat, index, "blue")

    source.updateData({
      remove: [oldSegmentId],
      add: [makeSegmentFeatureAt(index), makeSegmentFeatureAt(index + 1)],
    })
    updateLabelAt(index)
    updateLabelAt(index + 1)

    commitMarkersChange()
  }

  const hideGhostMarker = () => {
    ghostMarkerIndex.current = -1

    const marker = ghostMarker.current
    if (!marker) return
    marker.removeClassName("dragging")
    marker.getElement().hidden = true
  }

  const ghostMarkerFactory = () => {
    const marker = markerFactory("blue")
    marker.addClassName("ghost-marker")
    marker.getElement().hidden = true
    marker.setOffset([0, 8])

    marker.on("dragstart", () => {
      dragMode.current = "ghost"
      console.debug("Distance: Ghost marker materialized")
      marker.addClassName("dragging")
      batch(() => {
        insertMarkerAt(ghostMarkerIndex.current, marker.getLngLat())
      })
    })
    marker.on(
      "drag",
      throttle(
        () => {
          if (dragMode.current !== "ghost") return
          const entry = markers.current[ghostMarkerIndex.current]
          if (!entry) return
          const lngLat = marker.getLngLat()
          entry.marker.setLngLat(lngLat)
          updateMarkerDataAt(entry.index, lngLat)
        },
        16,
        { ensureLastCall: true },
      ),
    )
    marker.on("dragend", () => {
      dragMode.current = "none"
      hideGhostMarker()
    })
    marker.getElement().addEventListener("click", (e) => {
      e.stopPropagation()
      console.debug("Distance: Ghost marker clicked")
      batch(() => {
        insertMarkerAt(ghostMarkerIndex.current, marker.getLngLat())
        hideGhostMarker()
      })
    })
    return marker
  }

  const updateGhostMarkerPositionNow = (e: MapMouseEvent | MouseEvent) => {
    if (!active.peek()) return

    if (dragMode.current !== "none") return
    if (markers.current.length < 2) {
      hideGhostMarker()
      return
    }

    const marker = ghostMarker.current
    if (!marker) return
    if (marker.getElement().hidden) return

    const { clientX, clientY } = e instanceof MapMouseEvent ? e.originalEvent : e
    const mapRect = mapContainer.getBoundingClientRect()
    const point = new Point(
      clientX - mapRect.left,
      clientY - mapRect.top + 20, // offset for marker height
    )

    let minDistanceSq = Number.POSITIVE_INFINITY
    let closestPoint: Point | null = null
    ghostMarkerIndex.current = -1
    for (let i = 1; i < markers.current.length; i++) {
      const segmentClosestPoint = closestPointOnSegment(
        point,
        map.project(positions.current[i - 1]),
        map.project(positions.current[i]),
      )
      const dx = segmentClosestPoint.x - point.x
      const dy = segmentClosestPoint.y - point.y
      const distanceSq = dx * dx + dy * dy
      if (distanceSq < minDistanceSq) {
        minDistanceSq = distanceSq
        closestPoint = segmentClosestPoint
        ghostMarkerIndex.current = i
      }
    }
    if (ghostMarkerIndex.current > -1) {
      marker.setLngLat(map.unproject(closestPoint!))
    }

    const markerRect = marker.getElement().getBoundingClientRect()
    if (
      clientX < markerRect.left ||
      clientX > markerRect.right ||
      clientY < markerRect.top ||
      clientY > markerRect.bottom
    ) {
      hideGhostMarker()
    }
  }

  const updateGhostMarkerPosition = throttle(updateGhostMarkerPositionNow, 16, {
    ensureLastCall: true,
  })

  const resetState = () => {
    dragMode.current = "none"
    ghostMarker.current?.remove()
    ghostMarker.current = null
    ghostMarkerIndex.current = -1

    for (const { marker } of markers.current) marker.remove()
    markers.current.length = 0
    positions.current.length = 0

    for (const label of labels.current.values()) label.remove()
    labels.current.clear()
    source.updateData({ removeAll: true })

    totalDistance.value = 0
    markersCount.value = 0
  }

  useSignalEffect(() => {
    if (!active.value) return

    switchActionSidebar(map, sidebar)
    setPageTitle(t("javascripts.directions.distance"))
    addMapLayer(map, LAYER_ID)

    // Load markers from URL
    const line = getSearchParam("line")
    let loadedPositions: [number, number][] = []
    if (line) {
      try {
        loadedPositions = decodeLonLat(line, 5)
      } catch (error) {
        console.error("Distance: Failed to decode line", line, error)
      }
    }

    for (const [lon, lat] of loadedPositions) {
      addMarkerAtEnd([lon, lat], true)
    }

    console.debug("Distance: Loaded", loadedPositions.length, "points")

    rebuildSegmentsAndLabels()

    commitMarkersChange(false)

    // Focus on the markers if they're offscreen
    if (markers.current.length) {
      const first = markers.current[0]
      const firstLngLat = first?.marker.getLngLat()
      if (firstLngLat) {
        let markerBounds = new LngLatBounds(firstLngLat, firstLngLat)
        for (const entry of markers.current) {
          markerBounds = markerBounds.extend(entry.marker.getLngLat())
        }
        fitBoundsIfNeeded(map, markerBounds, {
          maxZoom: 16,
          minProportion: 0,
        })
      }
    }

    const onLineMouseEnter = (e: MapMouseEvent) => {
      if (dragMode.current !== "none") return
      if (markers.current.length < 2) return

      if (!ghostMarker.current)
        ghostMarker.current = ghostMarkerFactory().setLngLat([0, 0]).addTo(map)
      ghostMarker.current.getElement().hidden = false
      updateGhostMarkerPositionNow(e)
    }

    const onMapClick = (e: MapMouseEvent) => {
      batch(() => {
        addMarkerAtEnd(e.lngLat)
      })
    }

    map.on("click", onMapClick)
    map.on("mousemove", updateGhostMarkerPosition)
    map.on("mouseenter", LAYER_ID, onLineMouseEnter)

    return () => {
      map.off("click", onMapClick)
      map.off("mousemove", updateGhostMarkerPosition)
      map.off("mouseenter", LAYER_ID, onLineMouseEnter)

      removeMapLayer(map, LAYER_ID)
      resetState()
    }
  })

  return (
    <div class="sidebar-content">
      <div class="section">
        <SidebarHeader class="mb-2">
          <div>
            <i class="bi bi-signpost-2 me-1-5"></i>
            <span>{t("javascripts.directions.distance")}</span>:{" "}
            <span class="fw-semibold">{totalDistanceText.value}</span>
          </div>
        </SidebarHeader>

        <div class="d-flex flex-wrap gap-2">
          {markersCount.value > 0 ? (
            <button
              class="btn btn-sm btn-primary"
              type="button"
              onClick={clearMarkers}
            >
              {t("action.clear_markers")}
            </button>
          ) : null}

          <button
            class="btn btn-sm btn-soft"
            type="button"
            onClick={toggleUnit}
          >
            {unit.value === "metric"
              ? t("distance.switch_to_imperial")
              : t("distance.switch_to_metric")}
          </button>
        </div>
      </div>
    </div>
  )
}

export const getDistanceController = (map: MaplibreMap) => {
  const mapContainer = map.getContainer()
  const source = map.getSource<GeoJSONSource>(LAYER_ID)!
  const sidebar = getActionSidebar("distance")
  const active = signal(false)

  render(
    <DistanceSidebar
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
