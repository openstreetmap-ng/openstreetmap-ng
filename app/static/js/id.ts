import { apiUrl, primaryLanguage } from "./_config"
import { parentLoadSystemApp } from "./_system-app"
import { throttle } from "./_utils"

const container = document.querySelector("div.id-container")
if (!container) throw new Error("iD container not found")

parentLoadSystemApp((accessToken) => {
    // @ts-ignore
    const ctx = window.iD.coreContext()
    ctx.connection().apiConnections([])
    ctx.preauth({
        url: parent.location.origin,
        apiUrl: apiUrl,
        access_token: accessToken,
    })

    const id = ctx
        .embed(true)
        .assetPath(`/static-id/${container.dataset.version}/`)
        .locale(primaryLanguage)
        .containerNode(container)
        .init()

    const map = id.map()

    // On map move, send the new state to the parent
    map.on(
        "move.embed",
        throttle(() => {
            // Skip during introduction
            if (id.inIntro()) return

            const [lon, lat] = map.center()
            const zoom = map.zoom()
            parent.postMessage({ type: "mapState", source: "id", state: { lon, lat, zoom } }, "*")
        }, 250),
    )
})
