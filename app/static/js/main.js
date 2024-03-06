import "./_bootstrap.js"
import "./_i18n.js"

import { configureMainMap } from "./leaflet/_main-map.js"

const mapContainer = document.querySelector(".main-map")
if (mapContainer) configureMainMap(mapContainer)
