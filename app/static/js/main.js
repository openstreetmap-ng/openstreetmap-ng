import { homePoint } from "./_params.js"
import { Router } from "./_router.js"
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

const router = Router(
    new Map([
        ["/", null], // TODO: index
        ["/export", null], // TODO: export
        ["/directions", null], // TODO: directions
        ["/search", null], // TODO: search
        ["/query", null], // TODO: query
        ["/history", null], // TODO: history
        ["/history/nearby", null], // TODO: history
        ["/history/friends", null], // TODO: history
        ["/user/(?<display_name>[^/]+)/history", null], // TODO: history
        ["/note/new", null], // TODO: new note
        ["/note/(?<id>\\d+)", null], // TODO: note
        ["/node/(?<id>\\d+)", null], // TODO: browse
        ["/node/(?<id>\\d+)/history", null], // TODO: history
        ["/way/(?<id>\\d+)", null], // TODO: browse
        ["/way/(?<id>\\d+)/history", null], // TODO: history
        ["/relation/(?<id>\\d+)", null], // TODO: browse
        ["/relation/(?<id>\\d+)/history", null], // TODO: history
        ["/changeset/(?<id>\\d+)", null], // TODO: changeset
    ]),
)
