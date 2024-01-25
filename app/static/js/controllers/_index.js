import { switchActionSidebar } from "../_action-sidebar.js"
import { getPageTitle } from "../_title.js"

/**
 * Create a new index controller
 * @returns {object} Controller
 */
export const getIndexController = () => {
    return {
        load: () => {
            switchActionSidebar("index")
            document.title = getPageTitle()
        },
        unload: () => {
            // do nothing
        },
    }
}
