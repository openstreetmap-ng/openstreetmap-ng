import { Context } from "@rapideditor/rapid"
import { apiUrl, primaryLanguage, rapidVersion } from "./_params.js"

const rapidContainer = document.querySelector(".rapid-container")
if (rapidContainer) {
    const params = rapidContainer.dataset

    // Create and configure app context
    const ctx = new Context()
    ctx.preauth = {
        url: parent.location.origin,
        apiUrl: apiUrl,
        // biome-ignore lint/style/useNamingConvention: Not controlled by this project
        client_id: params.clientId,
        // biome-ignore lint/style/useNamingConvention: Not controlled by this project
        client_secret: params.clientSecret,
        // biome-ignore lint/style/useNamingConvention: Not controlled by this project
        access_token: params.accessToken,
    }

    ctx.containerNode = rapidContainer
    ctx.assetPath = `/static-rapid/${rapidVersion}/`
    ctx.embed(true)
    ctx.locale(primaryLanguage)

    ctx.initAsync().then(() => {
        const map = ctx.systems.map

        // Map emits 'draw' on full redraws, it's already throttled
        map.on("draw", () => {
            // Skip if in intro
            if (ctx.inIntro) return

            const [lon, lat] = map.center()
            const zoom = map.zoom()
            parent.postMessage({ type: "mapState", state: { lon, lat, zoom } }, "*")
        })
    })
}
