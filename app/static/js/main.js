import "./_i18n.js"

import { configureActionSidebars } from "./_action-sidebar.js"
import { homePoint } from "./_config.js"
import { configureRouter } from "./_router.js"
import { getChangesetController } from "./controllers/_changeset.js"
import { getExportController } from "./controllers/_export.js"
import { getIndexController } from "./controllers/_index.js"
import { getNewNoteController } from "./controllers/_new-note.js"
import { getNoteController } from "./controllers/_note.js"
import { configureFindHomeButton } from "./leaflet/_find-home.js"
import { getMainMap } from "./leaflet/_map.js"

const mapContainer = document.querySelector(".map-container")
const map = getMainMap(mapContainer.querySelector(".main-map"))

// Configure here instead of navbar to avoid global script dependency (navbar is global)
// Find home button is only available for the users with configured home location
if (homePoint) {
    const findHomeButton = document.querySelector(".find-home")
    if (findHomeButton) configureFindHomeButton(map, findHomeButton)
}

configureRouter(
    new Map([
        ["/", getIndexController()],
        ["/export", getExportController(map)],
        ["/directions", null], // TODO: directions
        ["/search", null], // TODO: search
        ["/query", null], // TODO: query
        ["(?:/history(?:/(?<scope>nearby|friends))?|/user/(?<display_name>[^/]+)/history)", null], // TODO: history
        ["/note/new", getNewNoteController(map)],
        ["/note/(?<id>\\d+)", getNoteController(map)],
        ["/changeset/(?<id>\\d+)", getChangesetController(map)],
        ["/(?<type>node|way|relation)/(?<id>\\d+)", null], // TODO: browse
        ["/(?<type>node|way|relation)/(?<id>\\d+)/history", null], // TODO: history
    ]),
)

configureActionSidebars()
