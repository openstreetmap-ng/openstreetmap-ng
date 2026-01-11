import { SidebarHeader } from "@index/_action-sidebar"
import { SidebarToggleControl } from "@index/sidebar/_toggle-button"
import { activeBaseLayerId, type LayerId } from "@lib/map/layers/layers"
import {
  effect,
  type ReadonlySignal,
  useSignal,
  useSignalEffect,
} from "@preact/signals"
import { t } from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"
import { render } from "preact"

/**
 * Zoom specification: number = min zoom, [min, max] = range, null = always visible
 * Legend entry: [zoom, icon] or [zoom, icon, translationKey]
 */
type ZoomSpec = number | readonly [min: number, max: number] | null
type LegendEntry =
  | readonly [zoom: ZoomSpec, icon: string]
  | readonly [zoom: ZoomSpec, icon: string, translationKey: string]

const LEGEND_DATA = {
  standard: [
    [6, "motorway"],
    [[6, 7], "mainroad", "main_road"],
    [[8, 8], "mainroad7", "main_road"],
    [[9, 11], "mainroad9", "main_road"],
    [12, "mainroad12", "main_road"],
    [13, "track"],
    [13, "bridleway"],
    [13, "cycleway"],
    [13, "footway"],
    [[8, 12], "rail"],
    [13, "rail13", "rail"],
    [13, "subway"],
    [13, "tram"],
    [12, "cable_car"],
    [12, "chair_lift"],
    [11, "runway"],
    [12, "apron"],
    [null, "admin"],
    [9, "forest"],
    [10, "wood"],
    [10, "golf"],
    [10, "park"],
    [8, "resident"],
    [10, "common"],
    [10, "retail"],
    [10, "industrial"],
    [10, "commercial"],
    [10, "heathland"],
    [7, "lake"],
    [10, "farm"],
    [10, "brownfield"],
    [11, "cemetery"],
    [11, "allotments"],
    [11, "pitch"],
    [11, "centre"],
    [11, "reserve"],
    [11, "military"],
    [12, "school"],
    [12, "building"],
    [12, "station"],
    [12, "summit"],
    [12, "tunnel"],
    [13, "bridge"],
    [15, "private"],
    [15, "destination"],
    [12, "construction"],
  ],
  cyclemap: [
    [[5, 11], "motorway"],
    [12, "motorway12", "motorway"],
    [[6, 11], "trunk"],
    [12, "trunk12", "trunk"],
    [[7, 11], "primary"],
    [12, "primary12", "primary"],
    [[9, 11], "secondary"],
    [12, "secondary12", "secondary"],
    [13, "track"],
    [[8, 19], "cycleway"],
    [[5, 12], "cycleway_national"],
    [13, "cycleway_national13", "cycleway_national"],
    [[5, 12], "cycleway_regional"],
    [13, "cycleway_regional13", "cycleway_regional"],
    [[8, 12], "cycleway_local"],
    [13, "cycleway_local13", "cycleway_local"],
    [13, "footway"],
    [[7, 13], "rail"],
    [14, "rail14", "rail"],
    [9, "forest"],
    [10, "common"],
    [7, "lake"],
    [14, "bicycle_shop"],
    [14, "bicycle_parking"],
    [16, "toilets"],
  ],
} as const satisfies Record<string, readonly LegendEntry[]>

type LegendLayerId = LayerId & keyof typeof LEGEND_DATA

const isLegendLayerId = (layerId: LayerId | null): layerId is LegendLayerId =>
  layerId !== null && Object.hasOwn(LEGEND_DATA, layerId)

const toZoomRange = (zoom: ZoomSpec): readonly [minZoom: number, maxZoom: number] =>
  zoom === null ? [0, 99] : typeof zoom === "number" ? [zoom, 99] : zoom

const LegendSidebar = ({
  map,
  active,
  close,
}: {
  map: MaplibreMap
  active: ReadonlySignal<boolean>
  close: () => void
}) => {
  const getZoom = () => Math.round(map.getZoom())
  const currentZoom = useSignal(getZoom())

  useSignalEffect(() => {
    if (!active.value) return

    const onZoomEnd = () => {
      currentZoom.value = getZoom()
    }
    map.on("zoomend", onZoomEnd)
    onZoomEnd()

    return () => map.off("zoomend", onZoomEnd)
  })

  if (!active.value) return null

  const baseLayerId = activeBaseLayerId.value
  if (!isLegendLayerId(baseLayerId)) return null

  const visibleEntries = LEGEND_DATA[baseLayerId as keyof typeof LEGEND_DATA].filter(
    (entry) => {
      const [zoom] = entry
      const [minZoom, maxZoom] = toZoomRange(zoom)
      return currentZoom.value >= minZoom && currentZoom.value <= maxZoom
    },
  )

  return (
    <div class="sidebar-content section">
      <SidebarHeader
        title={t("javascripts.key.title")}
        class="mb-2"
        onClose={close}
      />

      <table class="table table-sm table-borderless">
        <tbody>
          {visibleEntries.map((entry: LegendEntry) => {
            const [, icon, translationKey = icon] = entry
            return (
              <tr key={`${baseLayerId}:${icon}`}>
                <td>
                  <img
                    draggable={false}
                    loading="lazy"
                    src={`/static/img/legend/${baseLayerId}/${icon}.webp`}
                    alt=""
                  />
                </td>
                <td>{t(`site.key.table.entry.${translationKey}`)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export class LegendSidebarToggleControl extends SidebarToggleControl {
  public _container!: HTMLElement

  public constructor() {
    super("legend", "javascripts.key.tooltip")
  }

  public override onAdd(map: MaplibreMap) {
    const container = super.onAdd(map)

    render(
      <LegendSidebar
        map={map}
        active={this.active}
        close={this.close}
      />,
      this.sidebar,
    )

    effect(() => {
      if (isLegendLayerId(activeBaseLayerId.value)) {
        if (this.button.disabled) {
          this.button.disabled = false
          this.tooltip.setContent({
            ".tooltip-inner": t("javascripts.key.tooltip"),
          })
        }
        return
      }

      if (!this.button.disabled) {
        this.button.blur()
        this.button.disabled = true
        this.tooltip.setContent({
          ".tooltip-inner": t("javascripts.key.tooltip_disabled"),
        })
      }

      this.close()
    })

    this._container = container
    return container
  }
}
