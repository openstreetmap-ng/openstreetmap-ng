import type { MapLibreEvent } from "maplibre-gl"

declare module "maplibre-gl" {
  interface MapEventType {
    reloadnoteslayer: MapLibreEvent
  }
}
