import { useSidebar } from "@index/_action-sidebar"
import { zoomPrecision } from "@lib/coords"
import { boundsPadding } from "@lib/map/bounds"
import type { LonLatZoom } from "@lib/map/state"
import type { SearchDataValid } from "@lib/proto/search_pb"
import { SearchService } from "@lib/proto/search_pb"
import { type ReadonlySignal, useComputed } from "@preact/signals"
import { roundTo } from "@std/math/round-to"
import type { Map as MaplibreMap } from "maplibre-gl"

const getReverseRequest = (at: LonLatZoom) => {
  const precision = zoomPrecision(at.zoom)
  return {
    at: {
      lon: roundTo(at.lon, precision),
      lat: roundTo(at.lat, precision),
      zoom: Math.round(at.zoom),
    },
  }
}

const getSearchRequest = (map: MaplibreMap, q: string, local: boolean) => {
  const bounds = boundsPadding(map.getBounds(), -0.01)
  const [[minLon, minLat], [maxLon, maxLat]] = bounds.adjustAntiMeridian().toArray()
  return {
    query: q,
    bbox: { minLon, minLat, maxLon, maxLat },
    localOnly: local,
  }
}

export const useSidebarSearchRpc = ({
  map,
  q,
  at,
  local,
}: {
  map: MaplibreMap
  q: ReadonlySignal<string | undefined>
  at: ReadonlySignal<LonLatZoom | undefined>
  local: ReadonlySignal<boolean>
}) => {
  const search = useSidebar(
    useComputed(() => {
      const query = q.value
      return query ? getSearchRequest(map, query, local.value) : null
    }),
    SearchService.method.search,
    (r) => r.data,
  )

  const reverse = useSidebar(
    useComputed(() => {
      if (q.value) return null
      const p = at.value
      return p ? getReverseRequest(p) : null
    }),
    SearchService.method.reverse,
    (r) => r.data,
  )

  const resource = useComputed(() =>
    q.value ? search.resource.value : reverse.resource.value,
  )
  const data = useComputed<SearchDataValid | null>(() =>
    q.value ? search.data.value : reverse.data.value,
  )
  return { resource, data }
}
