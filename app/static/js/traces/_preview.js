import { createBasicMap } from "../leaflet/_basic-map.js";
import { antPath } from "leaflet-ant-path";

const tracesDetailsMapContainer = document.querySelector("#trace-map");
const coords = JSON.parse(tracesDetailsMapContainer.dataset.coords);

if (tracesDetailsMapContainer) {
  console.debug("Initializing trace preview map");
  const map = createBasicMap(tracesDetailsMapContainer);

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

