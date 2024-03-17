import "./_bootstrap.js"
import "./_i18n.js" // i18n must be loaded before other scripts

import "./_fixthemap.js"
import "./_welcome.js"
import { configureMainMap } from "./leaflet/_main-map.js"
import "./user/_login.js"
import "./user/_signup.js"
import "./user/_terms.js"

const mapContainer = document.querySelector(".main-map")
if (mapContainer) configureMainMap(mapContainer)
