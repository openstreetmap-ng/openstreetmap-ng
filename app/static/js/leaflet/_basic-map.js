import { getZoomControl } from "./_zoom-control.js";
import {
  addControlGroup,
  disableControlClickPropagation,
  getInitialMapState,
  setMapState,
} from "./_map-utils.js";
import { getGeolocateControl } from "./_geolocate-control.js";

/**
 * Get the basic map instance
 * @param {HTMLDivElement} container The container element
 * @returns {L.Map} Leaflet map
 */
export const createBasicMap = (container) => {
  const map = L.map(container, {
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

  return map;
};
