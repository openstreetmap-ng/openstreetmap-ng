import "./_i18n.js"

import { configureActionSidebars } from "./_action-sidebar.js"
import { homePoint } from "./_config.js"
import { getChangesetController } from "./index/_changeset.js"
import { getChangesetsHistoryController } from "./index/_changesets-history.js"
import { getElementController } from "./index/_element.js"
import { getExportController } from "./index/_export.js"
import { getIndexController } from "./index/_index.js"
import { getNewNoteController } from "./index/_new-note.js"
import { getNoteController } from "./index/_note.js"
import { getQueryFeaturesController } from "./index/_query-features.js"
import { configureRouter } from "./index/_router.js"
import { configureFindHomeButton } from "./leaflet/_find-home-button.js"
import { getMainMap } from "./leaflet/_main-map.js"

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
        ["/query", getQueryFeaturesController(map)],
        [
            "(?:/history(?:/(?<scope>nearby|friends))?|/user/(?<displayName>[^/]+)/history)",
            getChangesetsHistoryController(map),
        ],
        ["/note/new", getNewNoteController(map)],
        ["/note/(?<id>\\d+)", getNoteController(map)],
        ["/changeset/(?<id>\\d+)", getChangesetController(map)],
        ["/(?<type>node|way|relation)/(?<id>\\d+)(?:/history/(?<version>\\d+))?", getElementController(map)],
        ["/(?<type>node|way|relation)/(?<id>\\d+)/history", null], // TODO: history
    ]),
)

configureActionSidebars()
