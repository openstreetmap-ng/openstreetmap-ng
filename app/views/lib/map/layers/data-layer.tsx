import type { ElementTypeSlug } from "@index/element"
import { ElementRoute } from "@index/element"
import { routerNavigate } from "@index/router"
import { dataLayerLoading } from "@index/sidebar/layers"
import { MAP_QUERY_AREA_MAX_SIZE } from "@lib/config"
import { RenderElementsDataSchema } from "@lib/proto/element_pb"
import { qsEncode } from "@lib/qs"
import { fromBinaryValid } from "@lib/rpc"
import type { OSMNode, OSMWay } from "@lib/types"
import { signal } from "@preact/signals"
import { fail } from "@std/assert"
import { t } from "i18next"
import type {
  GeoJSONSource,
  LngLatBounds,
  MapLayerMouseEvent,
  Map as MaplibreMap,
} from "maplibre-gl"
import { MapAlertPanel, mountMapAlert } from "../alerts"
import { boundsContain, boundsPadding, boundsSize, boundsToString } from "../bounds"
import { clearMapHover, setMapHover } from "../hover"
import { convertRenderElementsData, renderObjects } from "../render-objects"
import {
  addLayerEventHandler,
  DATA_LAYER_CODE,
  DATA_LAYER_ID,
  emptyFeatureCollection,
  getExtendedLayerId,
  layersConfig,
  removeMapLayer,
} from "./layers"

const LAYER_ID = DATA_LAYER_ID
const LAYER_CODE = DATA_LAYER_CODE
const THEME_COLOR = "#38f"
const HOVER_THEME_COLOR = "#f90"
layersConfig.set(LAYER_ID, {
  specification: {
    type: "geojson",
    data: emptyFeatureCollection,
  },
  layerCode: LAYER_CODE,
  layerTypes: ["line", "circle"],
  layerOptions: {
    layout: {
      "line-cap": "round",
      "line-join": "round",
    },
    paint: {
      "line-color": [
        "case",
        ["boolean", ["feature-state", "hover"], false],
        HOVER_THEME_COLOR,
        THEME_COLOR,
      ],
      "line-width": 3,
      "circle-radius": 10,
      "circle-color": [
        "case",
        ["boolean", ["feature-state", "hover"], false],
        HOVER_THEME_COLOR,
        THEME_COLOR,
      ],
      "circle-opacity": [
        "case",
        ["boolean", ["feature-state", "hover"], false],
        0.4,
        0.2,
      ],
      "circle-stroke-color": [
        "case",
        ["boolean", ["feature-state", "hover"], false],
        HOVER_THEME_COLOR,
        THEME_COLOR,
      ],
      "circle-stroke-width": 3,
    },
  },
  priority: 100,
})

const LOAD_DATA_ALERT_THRESHOLD = 10_000

/** Configure the data layer for the given map */
export const configureDataLayer = (map: MaplibreMap) => {
  const source = map.getSource<GeoJSONSource>(LAYER_ID)!

  const loadDataAlertVisible = signal(false)
  const errorDataAlertVisible = signal(false)

  let enabled = false
  let abortController: AbortController | undefined
  let fetchedBounds: LngLatBounds | null = null
  let loadDataOverride = false

  const clearData = () => {
    fetchedBounds = null
    source.setData(emptyFeatureCollection)
    clearMapHover(map, LAYER_ID)
  }

  /** On feature click, navigate to the object page */
  const onFeatureClick = (e: MapLayerMouseEvent) => {
    const props = e.features![0].properties
    routerNavigate(ElementRoute, {
      type: props.type as ElementTypeSlug,
      id: BigInt(props.id),
    })
  }

  let hoveredFeatureId: number | null = null
  const onFeatureHover = (e: MapLayerMouseEvent) => {
    const feature = e.features![0]
    const featureId = feature.id as number
    if (hoveredFeatureId === featureId) return
    if (hoveredFeatureId) {
      map.removeFeatureState({ source: LAYER_ID, id: hoveredFeatureId })
    } else {
      setMapHover(map, LAYER_ID)
    }
    hoveredFeatureId = featureId
    map.setFeatureState({ source: LAYER_ID, id: hoveredFeatureId }, { hover: true })
  }
  const onFeatureLeave = () => {
    if (!hoveredFeatureId) return
    map.removeFeatureState({ source: LAYER_ID, id: hoveredFeatureId })
    hoveredFeatureId = null
    clearMapHover(map, LAYER_ID)
  }

  for (const type of ["fill", "line", "circle"] as const) {
    const extendedLayerId = getExtendedLayerId(LAYER_ID, type)
    map.on("click", extendedLayerId, onFeatureClick)
    map.on("mousemove", extendedLayerId, onFeatureHover)
    map.on("mouseleave", extendedLayerId, onFeatureLeave)
  }

  /** Load map data into the data layer */
  const loadData = (elements: (OSMNode | OSMWay)[]) => {
    console.debug("DataLayer: Loaded", elements.length, "elements")
    loadDataAlertVisible.value = false
    source.setData(renderObjects(elements, { renderAreas: false }))
  }

  /** On show data click, mark override and load data */
  const onShowDataButtonClick = () => {
    if (loadDataOverride) return
    console.debug("DataLayer: Show data clicked")
    loadDataOverride = true
    loadDataAlertVisible.value = false
    fetchedBounds = null
    updateLayer()
  }

  /** On hide data click, uncheck the data layer checkbox */
  const onHideDataButtonClick = () => {
    if (!enabled) return
    console.debug("DataLayer: Hide data clicked")
    removeMapLayer(map, LAYER_ID)
    loadDataAlertVisible.value = false
  }

  const DataLayerAlerts = () => (
    <>
      {errorDataAlertVisible.value && (
        <MapAlertPanel variant="warning">
          {t("map.data.too_much_data_error")}
          <i class="bi bi-zoom-in ms-1"></i>
        </MapAlertPanel>
      )}

      {loadDataAlertVisible.value && (
        <MapAlertPanel variant="warning">
          <p class="mb-2">{t("map.data.display_large_data_warning")}</p>
          <div class="d-flex justify-content-around align-items-center mx-3">
            <button
              class="btn btn-primary"
              type="button"
              onClick={onHideDataButtonClick}
            >
              <i class="bi bi-eye-slash-fill me-1"></i>
              {t("map.data.hide_map_data")}
            </button>
            {t("map.data.or")}
            <button
              class="btn btn-primary"
              type="button"
              onClick={onShowDataButtonClick}
            >
              {t("map.data.show_map_data")}
              <i class="bi bi-eye-fill ms-1"></i>
            </button>
          </div>
        </MapAlertPanel>
      )}
    </>
  )

  mountMapAlert(<DataLayerAlerts />)

  /** On map update, fetch the elements in view and update the data layer */
  const updateLayer = async () => {
    // Skip if the data layer is not visible
    if (!enabled) return

    // Abort any pending request
    abortController?.abort()
    abortController = new AbortController()

    const viewBounds = map.getBounds()

    // Skip updates if the view is satisfied
    if (
      fetchedBounds &&
      boundsContain(fetchedBounds, viewBounds) &&
      !loadDataAlertVisible.value
    )
      return

    // Pad the bounds to reduce refreshes
    const fetchBounds = boundsPadding(viewBounds, 0.3)

    // Skip updates if the area is too big
    const area = boundsSize(fetchBounds)
    if (area > MAP_QUERY_AREA_MAX_SIZE) {
      errorDataAlertVisible.value = true
      loadDataAlertVisible.value = false
      clearData()
      return
    }

    errorDataAlertVisible.value = false
    dataLayerLoading.value = true
    try {
      const resp = await fetch(
        `/api/web/map${qsEncode({
          bbox: boundsToString(fetchBounds),
          limit: loadDataOverride ? "" : LOAD_DATA_ALERT_THRESHOLD.toString(),
        })}`,
        { signal: abortController.signal, priority: "high" },
      )
      if (!resp.ok) {
        if (resp.status === 400) {
          errorDataAlertVisible.value = true
          loadDataAlertVisible.value = false
          clearData()
          return
        }
        fail(`${resp.status} ${resp.statusText}`)
      }

      const buffer = await resp.arrayBuffer()
      const render = fromBinaryValid(RenderElementsDataSchema, new Uint8Array(buffer))
      fetchedBounds = fetchBounds
      if (render.tooMuchData) {
        loadDataAlertVisible.value = true
      } else {
        loadData(convertRenderElementsData(render))
      }
    } catch (error) {
      if (error.name === "AbortError") return
      console.error("DataLayer: Failed to fetch", error)
      clearData()
    } finally {
      dataLayerLoading.value = false
    }
  }
  map.on("moveend", updateLayer)

  addLayerEventHandler((isAdded, eventLayerId) => {
    if (eventLayerId !== LAYER_ID) return
    enabled = isAdded
    if (isAdded) {
      updateLayer()
    } else {
      onFeatureLeave()
      errorDataAlertVisible.value = false
      loadDataAlertVisible.value = false
      abortController?.abort()
      clearData()
    }
  })
}
