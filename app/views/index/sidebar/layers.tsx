import { SidebarHeader } from "@index/_action-sidebar"
import { SidebarToggleControl } from "@index/sidebar/_toggle-button"
import { BTooltip } from "@lib/bootstrap"
import {
  isBreakpointDown,
  MAP_QUERY_AREA_MAX_SIZE,
  NOTE_QUERY_AREA_MAX_SIZE,
} from "@lib/config"
import { useDisposeEffect } from "@lib/dispose-scope"
import {
  globeProjectionStorage,
  layerOrderStorage,
  overlayOpacityStorage,
} from "@lib/local-storage"
import { boundsSize } from "@lib/map/bounds"
import { dataLayerPending } from "@lib/map/layers/data-layer"
import {
  AERIAL_LAYER_ID,
  activeBaseLayerId,
  addLayerEventHandler,
  addMapLayer,
  CYCLEMAP_LAYER_ID,
  CYCLOSM_LAYER_ID,
  DATA_LAYER_ID,
  GPS_LAYER_ID,
  HOT_LAYER_ID,
  hasMapLayer,
  type LayerId,
  LIBERTY_LAYER_ID,
  NOTES_LAYER_ID,
  removeMapLayer,
  STANDARD_LAYER_ID,
  TRACESTRACKTOPO_LAYER_ID,
  TRANSPORTMAP_LAYER_ID,
} from "@lib/map/layers/layers"
import { notesLayerPending } from "@lib/map/layers/notes-layer"
import { mainMap } from "@lib/map/main-map"
import { useComputed, useSignal, useSignalEffect } from "@preact/signals"
import { withoutAll } from "@std/collections/without-all"
import { t } from "i18next"
import type { LngLatBounds, MapLibreEvent } from "maplibre-gl"
import type { ComponentChildren, RefCallback } from "preact"
import { useEffect, useRef } from "preact/hooks"
import { MinimapPool } from "./minimap-pool"

const BASE_LAYERS = new Set([
  CYCLOSM_LAYER_ID,
  CYCLEMAP_LAYER_ID,
  TRANSPORTMAP_LAYER_ID,
  TRACESTRACKTOPO_LAYER_ID,
  LIBERTY_LAYER_ID,
  HOT_LAYER_ID,
])

const OVERLAY_LAYERS = new Set([
  AERIAL_LAYER_ID,
  NOTES_LAYER_ID,
  DATA_LAYER_ID,
  GPS_LAYER_ID,
])

// On mobile devices, show thumbnails instead of initializing MapLibre.
// Avoids "Too many active WebGL context even after destroyed".
const LAYER_THUMBNAILS = new Map<LayerId, string>([
  [AERIAL_LAYER_ID, "/static/img/layer/aerial.webp"],
])

type Minimap =
  | { kind: "map"; ref: RefCallback<HTMLDivElement> }
  | { kind: "image"; src: string }

const LayerTile = ({
  kind,
  active,
  onClick,
  minimap,
  children,
}: {
  kind: "base" | "overlay"
  active: boolean
  onClick: () => void
  minimap: Minimap
  children: ComponentChildren
}) => (
  <button
    type="button"
    class={`${kind} layer ${active ? "active" : ""}`}
    onClick={onClick}
    aria-current={kind === "base" ? active : undefined}
    aria-pressed={kind === "overlay" ? active : undefined}
  >
    <div
      class="map-container"
      {...(minimap.kind === "map" ? { ref: minimap.ref } : {})}
    >
      {minimap.kind === "image" && (
        <img
          src={minimap.src}
          loading="lazy"
        />
      )}
    </div>
    <span class="label">{children}</span>
  </button>
)

const ListLayerTile = ({
  active,
  onClick,
  minimap,
  children,
}: {
  active: boolean
  onClick: () => void
  minimap: Minimap
  children: ComponentChildren
}) => (
  <li class={`base layer ${active ? "active" : ""}`}>
    <button
      type="button"
      class="layer-button"
      onClick={onClick}
      aria-current={active}
    >
      <div
        class="map-container"
        {...(minimap.kind === "map" ? { ref: minimap.ref } : {})}
      >
        {minimap.kind === "image" && (
          <img
            src={minimap.src}
            loading="lazy"
          />
        )}
      </div>
      <span class="label">{children}</span>
    </button>
  </li>
)

const OverlayToggle = ({
  label,
  disabled = false,
  loading = false,
  disabledTooltipTitle,
  disabledTooltipPlacement,
  checked,
  onChange,
}: {
  label: ComponentChildren
  disabled?: boolean
  loading?: boolean
  disabledTooltipTitle?: string | undefined
  disabledTooltipPlacement?: "auto" | "top" | "bottom" | "left" | "right" | undefined
  checked: boolean
  onChange: (checked: boolean) => void
}) => (
  <BTooltip
    title={disabled ? disabledTooltipTitle : undefined}
    placement={disabledTooltipPlacement}
  >
    <div class={`form-check ${disabled ? "disabled" : ""}`}>
      <label class="form-check-label d-block">
        <input
          class="form-check-input"
          type="checkbox"
          disabled={disabled}
          checked={checked}
          onChange={(e) => onChange(e.currentTarget.checked)}
        />
        {label}
        {loading && (
          <output
            class="spinner-border text-body-secondary ms-1"
            aria-live="polite"
          >
            <span class="visually-hidden">{t("browse.start_rjs.loading")}</span>
          </output>
        )}
      </label>
    </div>
  </BTooltip>
)

export const LayersSidebar = ({ close }: { close: () => void }) => {
  const map = mainMap.value!
  const currentViewBounds = useSignal<LngLatBounds | null>(null)

  const orderedLayersCollapsed = useSignal(true)
  const orderedLayerIds = useComputed(() => {
    const ordered = new Set<LayerId>()
    for (const id of layerOrderStorage.value) {
      if (BASE_LAYERS.has(id)) {
        ordered.add(id)
      }
    }
    for (const id of BASE_LAYERS) {
      ordered.add(id)
    }
    return [...ordered]
  })

  const getInitialEnabledOverlays = () => {
    const initialOverlayState = new Set<LayerId>()
    for (const layerId of OVERLAY_LAYERS) {
      if (hasMapLayer(map, layerId)) initialOverlayState.add(layerId)
    }
    return initialOverlayState
  }
  const enabledOverlays = useSignal<ReadonlySet<LayerId>>(getInitialEnabledOverlays())

  const aerialOpacity = overlayOpacityStorage(AERIAL_LAYER_ID)

  const notesDisabled = useSignal(false)
  const notesRestoreOnEnableRef = useRef(false)

  const dataDisabled = useSignal(false)
  const dataRestoreOnEnableRef = useRef(false)

  const minimapRefs = useRef(new Map<LayerId, RefCallback<HTMLDivElement>>())
  const getMinimapRef = (layerId: LayerId) => {
    const existing = minimapRefs.current.get(layerId)
    if (existing) return existing

    const next: RefCallback<HTMLDivElement> = (el) => {
      if (el) MinimapPool.attach(layerId, el, map)
      else MinimapPool.detach(layerId)
    }
    minimapRefs.current.set(layerId, next)
    return next
  }

  const getLayerMinimap = (layerId: LayerId): Minimap => {
    if (isBreakpointDown("md")) {
      const thumbnail = LAYER_THUMBNAILS.get(layerId)
      if (thumbnail) return { kind: "image", src: thumbnail }
    }
    return { kind: "map", ref: getMinimapRef(layerId) }
  }

  const setBaseLayer = (layerId: LayerId) => {
    const activeLayerId = activeBaseLayerId.peek()
    if (activeLayerId === layerId) return

    if (layerId !== STANDARD_LAYER_ID) {
      const prevOrder = layerOrderStorage.peek()
      if (prevOrder[0] !== layerId) {
        layerOrderStorage.value = [layerId, ...withoutAll(prevOrder, [layerId])]
      }
    }

    if (activeLayerId) removeMapLayer(map, activeLayerId)
    addMapLayer(map, layerId)
  }

  const toggleOverlay = (layerId: LayerId, enabled: boolean) => {
    if (enabled === hasMapLayer(map, layerId)) return
    if (enabled) addMapLayer(map, layerId)
    else removeMapLayer(map, layerId)
  }

  useEffect(
    () =>
      addLayerEventHandler((isAdded, layerId) => {
        if (!OVERLAY_LAYERS.has(layerId)) return

        const next = new Set(enabledOverlays.peek())
        if (isAdded) next.add(layerId)
        else next.delete(layerId)
        enabledOverlays.value = next
      }),
    [],
  )

  useSignalEffect(() => {
    if (!enabledOverlays.value.has(AERIAL_LAYER_ID)) return
    map.setPaintProperty(AERIAL_LAYER_ID, "raster-opacity", aerialOpacity.value)
  })

  useDisposeEffect((scope) => {
    const onMoveEnd = (e?: MapLibreEvent) => {
      currentViewBounds.value = map.getBounds()
      MinimapPool.syncFrom(map, e ? "ease" : "jump")
    }
    scope.map(map, "moveend", onMoveEnd)
    onMoveEnd()
  }, [])

  useSignalEffect(() => {
    const bounds = currentViewBounds.value
    if (!bounds) return
    const areaSize = boundsSize(bounds)

    {
      const shouldDisable = areaSize > NOTE_QUERY_AREA_MAX_SIZE
      if (shouldDisable !== notesDisabled.value) {
        notesDisabled.value = shouldDisable
        if (shouldDisable) {
          if (hasMapLayer(map, NOTES_LAYER_ID)) {
            console.debug("LayersSidebar: Forcing unchecked state", NOTES_LAYER_ID)
            notesRestoreOnEnableRef.current = true
            removeMapLayer(map, NOTES_LAYER_ID)
          }
        } else if (notesRestoreOnEnableRef.current) {
          console.debug("LayersSidebar: Restoring overlay state", NOTES_LAYER_ID)
          notesRestoreOnEnableRef.current = false
          addMapLayer(map, NOTES_LAYER_ID)
        }
      }
    }

    {
      const shouldDisable = areaSize > MAP_QUERY_AREA_MAX_SIZE
      if (shouldDisable !== dataDisabled.value) {
        dataDisabled.value = shouldDisable
        if (shouldDisable) {
          if (hasMapLayer(map, DATA_LAYER_ID)) {
            console.debug("LayersSidebar: Forcing unchecked state", DATA_LAYER_ID)
            dataRestoreOnEnableRef.current = true
            removeMapLayer(map, DATA_LAYER_ID)
          }
        } else if (dataRestoreOnEnableRef.current) {
          console.debug("LayersSidebar: Restoring overlay state", DATA_LAYER_ID)
          dataRestoreOnEnableRef.current = false
          addMapLayer(map, DATA_LAYER_ID)
        }
      }
    }
  })

  return (
    <div class="sidebar-content">
      <div class="section">
        <SidebarHeader
          title={t("javascripts.map.layers.header")}
          class="mb-1"
          onClose={close}
        />

        <div class="form-check ms-1 mb-3">
          <label class="form-check-label d-block">
            <input
              class="form-check-input"
              type="checkbox"
              checked={globeProjectionStorage.value}
              onChange={(e) => (globeProjectionStorage.value = e.currentTarget.checked)}
            />
            {t("map.globe_view")}
            <BTooltip title={t("map.zoom_out_to_see_the_world_in_3d")}>
              <i class="bi bi-question-circle ms-1-5" />
            </BTooltip>
          </label>
        </div>

        <LayerTile
          kind="base"
          active={activeBaseLayerId.value === STANDARD_LAYER_ID}
          onClick={() => setBaseLayer(STANDARD_LAYER_ID)}
          minimap={getLayerMinimap(STANDARD_LAYER_ID)}
        >
          <img
            src="/static/img/favicon/256.webp"
            alt={t("alt.logo", { name: t("project_name") })}
          />
          {t("javascripts.map.base.standard")}
        </LayerTile>

        <hr />

        <div class={`layer-order ${orderedLayersCollapsed.value ? "collapsed" : ""}`}>
          <ul>
            {orderedLayerIds.value.map((layerId) => (
              <ListLayerTile
                key={layerId}
                active={activeBaseLayerId.value === layerId}
                onClick={() => setBaseLayer(layerId)}
                minimap={getLayerMinimap(layerId)}
              >
                {layerId === CYCLOSM_LAYER_ID && t("javascripts.map.base.cyclosm")}
                {layerId === CYCLEMAP_LAYER_ID && t("javascripts.map.base.cycle_map")}
                {layerId === TRANSPORTMAP_LAYER_ID &&
                  t("javascripts.map.base.transport_map")}
                {layerId === TRACESTRACKTOPO_LAYER_ID &&
                  t("javascripts.map.base.tracestracktop_topo")}
                {layerId === LIBERTY_LAYER_ID && (
                  <>
                    {t("map.layers.liberty")}
                    <span class="vector">{t("map.layers.vector")}</span>
                  </>
                )}
                {layerId === HOT_LAYER_ID && t("javascripts.map.base.hot")}
              </ListLayerTile>
            ))}
          </ul>

          <button
            class="btn btn-sm btn-link w-100"
            type="button"
            onClick={() =>
              (orderedLayersCollapsed.value = !orderedLayersCollapsed.value)
            }
          >
            <span class="show-more">
              {t("action.show_more")}
              <i class="bi bi-caret-down-fill small ms-1" />
            </span>
            <span class="show-less">
              {t("action.show_less")}
              <i class="bi bi-caret-up-fill small ms-1" />
            </span>
          </button>
        </div>
      </div>

      <div class="section">
        <h4>{t("map.overlays.title")}</h4>
        <p class="text-body-secondary small">{t("javascripts.map.layers.overlays")}</p>

        <div class="layer-settings mb-3">
          <LayerTile
            kind="overlay"
            active={enabledOverlays.value.has(AERIAL_LAYER_ID)}
            onClick={() =>
              toggleOverlay(
                AERIAL_LAYER_ID,
                !enabledOverlays.value.has(AERIAL_LAYER_ID),
              )
            }
            minimap={getLayerMinimap(AERIAL_LAYER_ID)}
          >
            {t("map.layers.esri_world_imagery")}
          </LayerTile>

          <div class="layer-settings-inner">
            <label class="form-label d-flex align-items-center gap-2 mb-0">
              {t("map.overlays.opacity")}:
              <input
                class="form-range"
                type="range"
                min="1"
                max="100"
                step="1"
                value={aerialOpacity.value * 100}
                onInput={(e) =>
                  (aerialOpacity.value = e.currentTarget.valueAsNumber / 100)
                }
              />
            </label>
          </div>
        </div>

        <div class="ms-1">
          <OverlayToggle
            label={t("javascripts.map.layers.notes")}
            disabled={notesDisabled.value}
            loading={notesLayerPending.value}
            disabledTooltipTitle={t("javascripts.site.map_notes_zoom_in_tooltip")}
            disabledTooltipPlacement="left"
            checked={enabledOverlays.value.has(NOTES_LAYER_ID)}
            onChange={(checked) => toggleOverlay(NOTES_LAYER_ID, checked)}
          />
          <OverlayToggle
            label={t("javascripts.map.layers.data")}
            disabled={dataDisabled.value}
            loading={dataLayerPending.value}
            disabledTooltipTitle={t("javascripts.site.map_data_zoom_in_tooltip")}
            disabledTooltipPlacement="left"
            checked={enabledOverlays.value.has(DATA_LAYER_ID)}
            onChange={(checked) => toggleOverlay(DATA_LAYER_ID, checked)}
          />
          <OverlayToggle
            label={t("traces.index.public_traces")}
            checked={enabledOverlays.value.has(GPS_LAYER_ID)}
            onChange={(checked) => toggleOverlay(GPS_LAYER_ID, checked)}
          />
        </div>
      </div>
    </div>
  )
}

export class LayerSidebarToggleControl extends SidebarToggleControl {
  public constructor() {
    super("layers", t("javascripts.map.layers.title"))
  }
}
