import { antPath } from "leaflet-ant-path";
import {
  addControlGroup,
  disableControlClickPropagation,
  getInitialMapState,
  setMapState,
} from "../leaflet/_map-utils";
import { getZoomControl } from "../leaflet/_zoom-control";
import { getGeolocateControl } from "../leaflet/_geolocate-control";

const tracesDetailsMapContainer = document.querySelector("#trace-map");

if (tracesDetailsMapContainer) {
  console.debug("Initializing trace preview map");
  const coords = JSON.parse(tracesDetailsMapContainer.dataset.coords);
  const map = L.map(tracesDetailsMapContainer, {
    zoomControl: false,
    maxBoundsViscosity: 1,
    minZoom: 3, // 2 would be better, but is buggy with leaflet animated pan
    maxBounds: L.latLngBounds(
      L.latLng(-85, Number.NEGATIVE_INFINITY),
      L.latLng(85, Number.POSITIVE_INFINITY)
    ),
  });

  // Disable Leaflet's attribution prefix
  map.attributionControl.setPrefix(false);

  // Add native controls
  map.addControl(L.control.scale());

  // Add controls
  addControlGroup(map, [getZoomControl(), getGeolocateControl()]);

  // Disable click propagation on controls
  disableControlClickPropagation(map);

  // TODO: support this on more maps
  const initialMapState = getInitialMapState(map);
  setMapState(map, initialMapState, { animate: false });

  // Trace path
  const options = {
    delay: 600,
    dashArray: [20, 60],
    weight: 3,
    color: "#999",
    pulseColor: "black",
    opacity: 0.9,
  };
  const path = antPath(coords, options).addTo(map);
  map.fitBounds(path.getBounds());
}
