import "./_bootstrap.js"
import "./_i18n.js"
import "./_welcome.js"
import { configureMainMap } from "./leaflet/_main-map.js"
import "./user/_login.js"
import "./user/_signup.js"
import "./user/_terms.js"

const mapContainer = document.querySelector(".main-map")
if (mapContainer) configureMainMap(mapContainer)
