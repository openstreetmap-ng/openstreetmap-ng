import { coreContext } from "iD"
import { encodeMapState } from "./_map-utils.js"
import { primaryLanguage } from "./_params.js"
import { throttle } from "./_utils.js"

const idContainer = document.querySelector(".id-container")
if (idContainer) {
    const params = idContainer.dataset
    const authUrl = params.authUrl
    const authAccessToken = params.authAccessToken
    const version = params.version

    // Create and configure app context
    const context = coreContext()
    context.connection().apiConnections([])
    context.preauth({
        url: authUrl,
        // biome-ignore lint/style/useNamingConvention: Not controlled by this project
        access_token: authAccessToken,
    })

    const id = context
        .embed(true)
        .assetPath(`static-id/${version}/`)
        .locale(primaryLanguage)
        .containerNode(idContainer)
        .init()

    const map = id.map()

    // On map move, update the location hash
    map.addEventListener(
        "move.embed",
        throttle(() => {
            if (id.inIntro()) return

            const [lon, lat] = map.center()
            const zoom = Math.floor(map.zoom())
            const latLonZoom = { lon: lon, lat: lat, zoom: zoom }

            // TODO: parent.updateLinks(latLonZoom, zoom)

            parent.location.hash = encodeMapState(latLonZoom)
        }, 250),
    )
}
