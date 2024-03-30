import { apiUrl, idVersion, primaryLanguage } from "./_config.js"
import { parentLoadSystemApp } from "./_system-app.js"
import { throttle } from "./_utils.js"

const idContainer = document.querySelector(".id-container")
if (!idContainer) throw new Error("iD container not found")

parentLoadSystemApp((accessToken) => {
    const ctx = window.iD.coreContext()
    ctx.connection().apiConnections([])
    ctx.preauth({
        url: parent.location.origin,
        apiUrl: apiUrl,
        // biome-ignore lint/style/useNamingConvention:
        access_token: accessToken,
    })

    const id = ctx
        .embed(true)
        .assetPath(`/static-id/${idVersion}/`)
        .locale(primaryLanguage)
        .containerNode(idContainer)
        .init()

    const map = id.map()

    // On map move, send the new state to the parent
    map.on(
        "move.embed",
        throttle(() => {
            // Skip if in intro
            if (id.inIntro()) return

            const [lon, lat] = map.center()
            const zoom = map.zoom()
            parent.postMessage({ type: "mapState", source: "id", state: { lon, lat, zoom } }, "*")
        }, 250),
    )
})
