import "maplibre-gl"

declare module "maplibre-gl" {
  interface MapEventType {
    reloadnoteslayer: MapLibreEvent
  }
}
