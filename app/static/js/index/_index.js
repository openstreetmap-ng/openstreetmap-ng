import * as L from "leaflet"
import { switchActionSidebar } from "../_action-sidebar.js"
import { getPageTitle } from "../_title.js"

/**
 * Create a new index controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getIndexController = (map) => {
    return {
        load: () => {
            switchActionSidebar(map, "index")
            document.title = getPageTitle()
        },
        unload: () => {
            // do nothing
        },
    }
}
