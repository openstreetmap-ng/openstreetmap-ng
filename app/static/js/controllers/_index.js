import { getPageTitle } from "../_title.js"
import { switchActionSidebar } from "./_action-sidebar.js"

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
