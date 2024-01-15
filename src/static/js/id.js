import { coreContext } from "iD"
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

    // On map move, send the new state to the parent
    // TODO: isn't there moveend event?
    map.addEventListener(
        "move.embed",
        throttle(() => {
            // Skip if in intro
            if (id.inIntro()) return

            const [lon, lat] = map.center()
            const zoom = Math.floor(map.zoom())
            parent.postMessage({ type: "mapState", source: "id", state: { lon, lat, zoom } }, "*")
        }, 250),
    )
}
