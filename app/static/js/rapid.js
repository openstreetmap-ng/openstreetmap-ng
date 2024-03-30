import { apiUrl, primaryLanguage, rapidVersion } from "./_config.js"
import { parentLoadSystemApp } from "./_system-app.js"

const rapidContainer = document.querySelector(".rapid-container")
if (!rapidContainer) throw new Error("Rapid container not found")

parentLoadSystemApp((accessToken) => {
    const ctx = new window.Rapid.Context()
    ctx.preauth = {
        url: parent.location.origin,
        apiUrl: apiUrl,
        // biome-ignore lint/style/useNamingConvention:
        access_token: accessToken,
    }

    ctx.containerNode = rapidContainer
    ctx.assetPath = `/static-rapid/${rapidVersion}/`
    ctx.locale = primaryLanguage
    ctx.embed(true)

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
})
