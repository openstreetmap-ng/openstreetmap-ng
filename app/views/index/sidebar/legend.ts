import { SidebarToggleControl } from "@index/sidebar/_toggle-button"
import { addLayerEventHandler, type LayerId } from "@lib/map/layers/layers"
import { getMapBaseLayerId } from "@lib/map/state"
import i18next from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"

/**
 * Zoom specification: number = min zoom, [min, max] = range, null = always visible
 * Legend entry: [zoom, icon] or [zoom, icon, translationKey]
 */
type ZoomSpec = number | readonly [min: number, max: number] | null
type LegendEntry =
    | readonly [zoom: ZoomSpec, icon: string]
    | readonly [zoom: ZoomSpec, icon: string, translationKey: string]

type LegendLayerId = "standard" | "cyclemap"

const LEGEND_DATA: Record<LegendLayerId, readonly LegendEntry[]> = {
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
}

/** Check if a layer has legend data available */
const hasLegend = (layerId: LayerId): boolean => layerId in LEGEND_DATA

interface RowInfo {
    element: HTMLTableRowElement
    layerId: LegendLayerId
    minZoom: number
    maxZoom: number
}

export class LegendSidebarToggleControl extends SidebarToggleControl {
    public _container!: HTMLElement

    public constructor() {
        super("legend", "javascripts.key.tooltip")
    }

    public override onAdd(map: MaplibreMap) {
        const container = super.onAdd(map)
        const button = container.querySelector("button")!
        const sidebarContent = this.sidebar.querySelector(".sidebar-content")!

        // State for lazy generation
        let rows: RowInfo[] | undefined

        /** Generate table and all rows (runs once on first open) */
        const generateLegend = (): RowInfo[] => {
            const table = document.createElement("table")
            table.className = "table table-sm table-borderless"
            const tbody = table.appendChild(document.createElement("tbody"))

            const result: RowInfo[] = []

            for (const layerId of Object.keys(LEGEND_DATA) as LegendLayerId[]) {
                for (const entry of LEGEND_DATA[layerId]) {
                    const [zoom, icon, translationKey = icon] = entry

                    const tr = document.createElement("tr")
                    const imgCell = tr.insertCell()
                    const img = imgCell.appendChild(document.createElement("img"))
                    img.draggable = false
                    img.loading = "lazy"
                    img.src = `/static/img/legend/${layerId}/${icon}.webp`
                    tr.insertCell().textContent = i18next.t(
                        `site.key.table.entry.${translationKey}`,
                    )

                    const [minZoom, maxZoom] =
                        zoom === null
                            ? [0, 99]
                            : typeof zoom === "number"
                              ? [zoom, 99]
                              : zoom

                    result.push({ element: tr, layerId, minZoom, maxZoom })
                    tbody.appendChild(tr)
                }
            }

            sidebarContent.appendChild(table)
            return result
        }

        // On sidebar shown, update the sidebar
        button.addEventListener("click", () => {
            if (button.classList.contains("active")) updateSidebar()
        })

        // On base layer change, update availability and refresh content
        addLayerEventHandler((isAdded, layerId, config) => {
            if (!(isAdded && config.isBaseLayer)) return
            const isLegendAvailable = hasLegend(layerId)
            if (isLegendAvailable) {
                if (button.disabled) {
                    button.disabled = false
                    this.tooltip.setContent({
                        ".tooltip-inner": i18next.t("javascripts.key.tooltip"),
                    })
                }
                updateSidebar()
                return
            }

            if (!button.disabled) {
                button.blur()
                button.disabled = true
                this.tooltip.setContent({
                    ".tooltip-inner": i18next.t("javascripts.key.tooltip_disabled"),
                })
            }

            // Uncheck the input if checked
            if (button.classList.contains("active")) {
                button.click()
            }
        })

        /** Update row visibility based on active layer and zoom */
        const updateSidebar = () => {
            if (!button.classList.contains("active")) return

            const activeLayerId = getMapBaseLayerId(map)
            const isLegendAvailable = activeLayerId !== null && hasLegend(activeLayerId)
            if (!isLegendAvailable) return

            // Lazy generation
            rows ??= generateLegend()

            const currentZoom = map.getZoom() | 0
            for (const { element, layerId, minZoom, maxZoom } of rows) {
                const isVisible =
                    layerId === activeLayerId &&
                    currentZoom >= minZoom &&
                    currentZoom <= maxZoom
                element.classList.toggle("d-none", !isVisible)
            }
        }
        map.on("zoomend", updateSidebar)

        this._container = container
        return container
    }
}
