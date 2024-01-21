import { switchActionSidebar } from "./_utils.js"

const originalTitle = document.title

export const getIndexController = () => {
    return {
        load: () => {
            switchActionSidebar("index")
            document.title = originalTitle
        },
        unload: () => {
            // do nothing
        },
    }
}
