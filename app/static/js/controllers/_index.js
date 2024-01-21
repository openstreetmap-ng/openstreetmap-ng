import { switchActionSidebar } from "./_utils.js"

export const getIndexController = () => {
    return {
        load: () => switchActionSidebar("index"),
        unload: () => {
            // do nothing
        },
    }
}
