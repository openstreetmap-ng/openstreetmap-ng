import { SidebarHeader } from "@index/_action-sidebar"
import { defineRoute } from "@index/router"
import { queryParam } from "@lib/codecs"
import { type Scheduled, useDisposeEffect } from "@lib/dispose-scope"
import { formatDistance, isMetricUnit } from "@lib/format"
import { fitBoundsIfNeeded } from "@lib/map/bounds"
import { closestPointOnSegment } from "@lib/map/geometry"
import {
  emptyFeatureCollection,
  type LayerId,
  layersConfig,
} from "@lib/map/layers/layers"
import {
  getMarkerIconElement,
  MARKER_ICON_ANCHOR,
  type MarkerColor,
} from "@lib/map/marker"
import { type Polyline, polylineEquals } from "@lib/polyline"
import { setPageTitle } from "@lib/title"
import { batch, type Signal, useSignal, useSignalEffect } from "@preact/signals"
import { assertEquals, assertGreater } from "@std/assert"
import type { Feature, LineString } from "geojson"
import { t } from "i18next"
import {
  type GeoJSONFeatureDiff,
  type GeoJSONSource,
  type GeoJSONSourceDiff,
  type LngLat,
  LngLatBounds,
  type LngLatLike,
  type Map as MaplibreMap,
  Marker,
  Point,
} from "maplibre-gl"
import { useRef } from "preact/hooks"

type MarkerEntry = {
  id: number
  marker: Marker
  label: DistanceLabel | null
}

interface DistanceLabel extends Marker {
  distance: number
}

const LINE_PRECISION = 5
const GHOST_POINTER_Y_OFFSET_PX = 20
const GHOST_QUERY_RADIUS_PX = 20

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
  line,
}: {
  map: MaplibreMap
  line: Signal<Polyline | undefined>
}) => {
  setPageTitle(t("javascripts.directions.distance"))
  const source = map.getSource<GeoJSONSource>(LAYER_ID)!

  const unit = useSignal<"metric" | "imperial">(isMetricUnit() ? "metric" : "imperial")
  const markersCount = useSignal(0)
  const totalDistance = useSignal(0)

  const updateMarkerDataFn = useRef<Scheduled<typeof updateMarkerDataNow>>()
  const updateGhostPositionFn = useRef<Scheduled<typeof updateGhostPositionNow>>()

  const nextMarkerId = useRef(0)
  const markers = useRef<MarkerEntry[]>([])
  const markerIdToIndex = useRef<Map<number, number>>(new Map())
  const ghostMarker = useRef<Marker | null>(null)
  const ghostEndMarkerId = useRef<number | null>(null)
  const ghostMaterializedMarkerId = useRef<number | null>(null)
  const isDragging = useRef(false)

  const computeLine = () => {
    const out: (readonly [lon: number, lat: number])[] = []
    for (const entry of markers.current) {
      const { lng, lat } = entry.marker.getLngLat()
      out.push([lng, lat])
    }
    return out.length ? (out as Polyline) : undefined
  }

  const updateLine = () => {
    const currentLine = computeLine()
    if (!polylineEquals(line.peek(), currentLine, LINE_PRECISION))
      line.value = currentLine
  }

  const setMarkerIcon = (marker: Marker, color: MarkerColor) => {
    marker.getElement().replaceChildren(...getMarkerIconElement(color, true).children)
  }

  const refreshEndpointIcons = () => {
    const count = markers.current.length
    if (count === 0) return
    setMarkerIcon(markers.current[0].marker, "green")
    if (count === 1) return
    setMarkerIcon(markers.current[count - 1].marker, "red")
  }

  const commitMarkersChange = (updateUrl = true) => {
    refreshEndpointIcons()
    markersCount.value = markers.current.length
    if (updateUrl) updateLine()
  }

  const reindexMarkersFrom = (startIndex: number) => {
    for (let i = startIndex; i < markers.current.length; i++) {
      const entry = markers.current[i]
      markerIdToIndex.current.set(entry.id, i)
    }
  }

  const createLabel = () => {
    const label = new Marker({
      anchor: "center",
      element: document.createElement("div"),
      className: "distance-label",
    })
      .setLngLat([0, 0])
      .addTo(map) as DistanceLabel
    label.distance = 0
    return label
  }

  const removeLabel = (endIndex: number) => {
    assertGreater(endIndex, 0)
    const label = markers.current[endIndex].label!
    totalDistance.value = totalDistance.peek() - label.distance
    label.remove()
    markers.current[endIndex].label = null
  }

  const updateLabel = (endIndex: number) => {
    assertGreater(endIndex, 0)
    const startEntry = markers.current[endIndex - 1]
    const endEntry = markers.current[endIndex]
    const startLngLat = startEntry.marker.getLngLat()
    const endLngLat = endEntry.marker.getLngLat()

    const startScreenPoint = map.project(startLngLat)
    const endScreenPoint = map.project(endLngLat)

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

    const newDistance = startLngLat.distanceTo(endLngLat)

    const label = endEntry.label!
    totalDistance.value = totalDistance.peek() + (newDistance - label.distance)
    label.distance = newDistance
    label.setLngLat(middlePoint)
    label.setRotation((angle * 180) / Math.PI)
    label.getElement().textContent = formatDistance(newDistance, unit.peek())
  }

  const segmentCoords = (endIndex: number) => {
    assertGreater(endIndex, 0)
    const startLngLat = markers.current[endIndex - 1].marker.getLngLat()
    const endLngLat = markers.current[endIndex].marker.getLngLat()
    return [
      [startLngLat.lng, startLngLat.lat],
      [endLngLat.lng, endLngLat.lat],
    ]
  }

  const makeSegmentFeature = (endIndex: number): Feature<LineString> => ({
    type: "Feature",
    id: markers.current[endIndex].id,
    properties: {},
    geometry: {
      type: "LineString",
      coordinates: segmentCoords(endIndex),
    },
  })

  const makeSegmentUpdate = (endIndex: number): GeoJSONFeatureDiff => ({
    id: markers.current[endIndex].id,
    newGeometry: {
      type: "LineString",
      coordinates: segmentCoords(endIndex),
    },
  })

  const updateSegmentsAround = (markerIndex: number) => {
    const count = markers.current.length
    if (count < 2) return

    const update: GeoJSONFeatureDiff[] = []
    if (markerIndex > 0) update.push(makeSegmentUpdate(markerIndex))
    if (markerIndex < count - 1) update.push(makeSegmentUpdate(markerIndex + 1))
    source.updateData({ update })

    if (markerIndex > 0) updateLabel(markerIndex)
    if (markerIndex < count - 1) updateLabel(markerIndex + 1)
  }

  const rebuildSegmentsAndLabels = () => {
    assertEquals(totalDistance.peek(), 0)

    const segments: Feature<LineString>[] = []
    for (let endIndex = 1; endIndex < markers.current.length; endIndex++) {
      markers.current[endIndex].label!.distance = 0
      updateLabel(endIndex)
      segments.push(makeSegmentFeature(endIndex))
    }

    source.setData({ type: "FeatureCollection", features: segments })
  }

  const clearMarkers = () => {
    if (markers.current.length) {
      console.debug("Distance: Clear markers")
    }
    resetState()
    updateLine()
  }

  const toggleUnit = () => {
    const next = unit.peek() === "metric" ? "imperial" : "metric"
    console.debug("Distance: Unit toggled", next)
    unit.value = next

    for (let i = 1; i < markers.current.length; i++) {
      const label = markers.current[i].label!
      label.getElement().textContent = formatDistance(label.distance, next)
    }
  }

  const removeMarker = (index: number) => {
    console.debug("Distance: Marker removed", index)
    hideGhostMarker()

    const countBefore = markers.current.length
    const target = markers.current[index]

    let segmentIdToRemove: number | null = null
    if (countBefore > 1) {
      const segmentEndIndexToRemove = Math.max(index, 1)
      segmentIdToRemove = markers.current[segmentEndIndexToRemove].id
      removeLabel(segmentEndIndexToRemove)
    }

    target.marker.remove()
    markerIdToIndex.current.delete(target.id)
    markers.current.splice(index, 1)
    reindexMarkersFrom(index)

    if (segmentIdToRemove !== null) {
      const diff: GeoJSONSourceDiff = { remove: [segmentIdToRemove] }
      const shouldUpdateBridge = index > 0 && index < countBefore - 1
      if (shouldUpdateBridge) {
        diff.update = [makeSegmentUpdate(index)]
        updateLabel(index)
      }
      source.updateData(diff)
    }

    commitMarkersChange()
  }

  const markerFactory = (color: MarkerColor) =>
    new Marker({
      anchor: MARKER_ICON_ANCHOR,
      element: getMarkerIconElement(color, true),
      className: "distance-marker",
      draggable: true,
    })

  const updateMarkerDataNow = (id: number, lngLat: LngLat) => {
    const index = markerIdToIndex.current.get(id)!
    markers.current[index].marker.setLngLat(lngLat)
    updateSegmentsAround(index)
  }

  const createMarkerEntry = (lngLat: LngLatLike, index: number, color: MarkerColor) => {
    const id = nextMarkerId.current++
    const marker = markerFactory(color).setLngLat(lngLat).addTo(map)

    const entry: MarkerEntry = {
      id,
      marker,
      label: index > 0 ? createLabel() : null,
    }

    marker.on("dragstart", () => {
      isDragging.current = true
      hideGhostMarker()
    })
    marker.on("drag", () => updateMarkerDataFn.current!(id, marker.getLngLat()))
    marker.on("dragend", () => {
      isDragging.current = false
      updateMarkerDataFn.current!.flush()
      updateLine()
    })
    marker.getElement().addEventListener("click", (e) => {
      e.stopPropagation()
      batch(() => {
        removeMarker(markerIdToIndex.current.get(id)!)
      })
    })

    if (index === markers.current.length) {
      markers.current.push(entry)
      markerIdToIndex.current.set(entry.id, index)
    } else {
      markers.current.splice(index, 0, entry)
      reindexMarkersFrom(index)
    }
    return entry
  }

  const appendMarker = (lngLat: LngLatLike, skipUpdates = false, updateUrl = true) => {
    const prevCount = markers.current.length
    console.debug("Distance: Marker created", lngLat, skipUpdates)
    if (skipUpdates) {
      return createMarkerEntry(lngLat, prevCount, "blue").id
    }

    if (prevCount >= 2) {
      setMarkerIcon(markers.current[prevCount - 1].marker, "blue")
    }

    const color = prevCount === 0 ? "green" : "red"
    const entry = createMarkerEntry(lngLat, prevCount, color)

    if (prevCount > 0) {
      const segmentEndIndex = prevCount
      source.updateData({ add: [makeSegmentFeature(segmentEndIndex)] })
      updateLabel(segmentEndIndex)
    }

    commitMarkersChange(updateUrl)
    return entry.id
  }

  const insertMarker = (index: number, lngLat: LngLat, updateUrl = true) => {
    console.debug("Distance: Marker inserted", index, lngLat.lng, lngLat.lat)
    if (index <= 0 || index >= markers.current.length) {
      return appendMarker(lngLat, false, updateUrl)
    }

    const inserted = createMarkerEntry(lngLat, index, "blue")

    source.updateData({
      add: [makeSegmentFeature(index)],
      update: [makeSegmentUpdate(index + 1)],
    })
    updateLabel(index)
    updateLabel(index + 1)

    commitMarkersChange(updateUrl)
    return inserted.id
  }

  const hideGhostMarker = () => {
    ghostEndMarkerId.current = null
    ghostMaterializedMarkerId.current = null

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
      isDragging.current = true
      console.debug("Distance: Ghost marker materialized")
      marker.addClassName("dragging")
      batch(() => {
        const endId = ghostEndMarkerId.current!
        const endIndex = markerIdToIndex.current.get(endId)!
        ghostMaterializedMarkerId.current = insertMarker(
          endIndex,
          marker.getLngLat(),
          false,
        )
      })
    })
    marker.on("drag", () => {
      const materializedId = ghostMaterializedMarkerId.current!
      const lngLat = marker.getLngLat()
      updateMarkerDataFn.current!(materializedId, lngLat)
    })
    marker.on("dragend", () => {
      isDragging.current = false
      updateMarkerDataFn.current!.flush()
      hideGhostMarker()
      updateLine()
    })
    marker.getElement().addEventListener("click", (e) => {
      e.stopPropagation()
      console.debug("Distance: Ghost marker clicked")
      batch(() => {
        const endId = ghostEndMarkerId.current!
        const endIndex = markerIdToIndex.current.get(endId)!
        insertMarker(endIndex, marker.getLngLat(), false)
        hideGhostMarker()
      })
      updateLine()
    })
    return marker
  }

  const updateGhostPositionNow = (x: number, y: number) => {
    if (isDragging.current) return
    if (markers.current.length < 2) {
      hideGhostMarker()
      return
    }

    const hitPoint = new Point(x, y + GHOST_POINTER_Y_OFFSET_PX)
    const r = GHOST_QUERY_RADIUS_PX
    const features = map.queryRenderedFeatures(
      [
        [hitPoint.x - r, hitPoint.y - r],
        [hitPoint.x + r, hitPoint.y + r],
      ],
      { layers: [LAYER_ID] },
    )

    if (!features.length) {
      hideGhostMarker()
      return
    }

    ghostMarker.current ??= ghostMarkerFactory().setLngLat([0, 0]).addTo(map)
    const marker = ghostMarker.current
    marker.getElement().hidden = false

    const firstSegmentId = Number(features[0].id)
    const firstEndIndex = markerIdToIndex.current.get(firstSegmentId)!
    const firstStartLngLat = markers.current[firstEndIndex - 1].marker.getLngLat()
    const firstEndLngLat = markers.current[firstEndIndex].marker.getLngLat()
    let bestEndId = firstSegmentId
    let bestClosestPoint = closestPointOnSegment(
      hitPoint,
      map.project(firstStartLngLat),
      map.project(firstEndLngLat),
    )
    let bestDistanceSq =
      (bestClosestPoint.x - hitPoint.x) ** 2 + (bestClosestPoint.y - hitPoint.y) ** 2

    for (let i = 1; i < features.length; i++) {
      const segmentId = Number(features[i].id)
      const endIndex = markerIdToIndex.current.get(segmentId)!
      const startLngLat = markers.current[endIndex - 1].marker.getLngLat()
      const endLngLat = markers.current[endIndex].marker.getLngLat()
      const closestPoint = closestPointOnSegment(
        hitPoint,
        map.project(startLngLat),
        map.project(endLngLat),
      )
      const distanceSq =
        (closestPoint.x - hitPoint.x) ** 2 + (closestPoint.y - hitPoint.y) ** 2
      if (distanceSq >= bestDistanceSq) continue
      bestDistanceSq = distanceSq
      bestEndId = segmentId
      bestClosestPoint = closestPoint
    }

    ghostEndMarkerId.current = bestEndId
    marker.setLngLat(map.unproject(bestClosestPoint))
  }

  const resetState = () => {
    nextMarkerId.current = 0
    for (const entry of markers.current) {
      entry.marker.remove()
      entry.label?.remove()
    }
    markers.current.length = 0
    markerIdToIndex.current.clear()
    source.setData(emptyFeatureCollection)

    ghostMarker.current?.remove()
    ghostMarker.current = null
    ghostEndMarkerId.current = null
    ghostMaterializedMarkerId.current = null
    isDragging.current = false

    markersCount.value = 0
    totalDistance.value = 0
  }

  const applyUrlLine = (line: Polyline | undefined) => {
    resetState()

    line ??= []
    console.debug("Distance: Loaded", line.length, "points")
    if (!line.length) return

    for (const [lon, lat] of line) {
      appendMarker([lon, lat], true)
    }

    rebuildSegmentsAndLabels()
    commitMarkersChange(false)

    // Focus on the markers if they're offscreen
    const [firstLon, firstLat] = line[0]
    const markerBounds = new LngLatBounds([firstLon, firstLat, firstLon, firstLat])
    for (let i = 1; i < line.length; i++) {
      const [lon, lat] = line[i]
      markerBounds.extend([lon, lat])
    }
    fitBoundsIfNeeded(map, markerBounds, {
      maxZoom: 16,
      minProportion: 0,
    })
  }

  useDisposeEffect((scope) => {
    scope.mapLayerLifecycle(map, LAYER_ID)

    updateMarkerDataFn.current = scope.frame((_, id, lngLat) => {
      updateMarkerDataNow(id, lngLat)
    })
    updateGhostPositionFn.current = scope.frame((_, x, y) => {
      updateGhostPositionNow(x, y)
    })

    scope.defer(() => {
      resetState()
    })

    scope.map(map, "click", (e) => {
      batch(() => {
        appendMarker(e.lngLat)
      })
    })
    scope.map(map, "mousemove", (e) => {
      updateGhostPositionFn.current!(e.point.x, e.point.y)
    })
  }, [])

  // Effect: apply external URL changes.
  useSignalEffect(() => {
    const nextLine = line.value
    const currentLine = computeLine()
    if (polylineEquals(nextLine, currentLine, LINE_PRECISION)) return
    applyUrlLine(nextLine)
  })

  return (
    <div class="sidebar-content">
      <div class="section">
        <SidebarHeader class="mb-2">
          <div>
            <i class="bi bi-signpost-2 me-1-5"></i>
            <span>{t("javascripts.directions.distance")}</span>:
            <span class="fw-semibold ms-1">
              {formatDistance(totalDistance.value, unit.value)}
            </span>
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

export const DistanceRoute = defineRoute({
  id: "distance",
  path: "/distance",
  query: { line: queryParam.polyline(LINE_PRECISION) },
  sidebarOverlay: true,
  Component: DistanceSidebar,
})
