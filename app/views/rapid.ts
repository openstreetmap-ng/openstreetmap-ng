import { config, primaryLanguage } from "./lib/config"
import { parentLoadSystemApp } from "./lib/system-app"

const container = document.querySelector("div.rapid-container")
if (!container) throw new Error("Rapid container not found")

parentLoadSystemApp((accessToken, parentOrigin) => {
    // @ts-ignore
    const ctx = new window.Rapid.Context()
    ctx.preauth = {
        url: parentOrigin,
        apiUrl: config.apiUrl,
        access_token: accessToken,
    }

    ctx.containerNode = container
    ctx.assetPath = `/static-rapid/${container.dataset.version}/`
    ctx.locale = primaryLanguage
    ctx.embed(true)

    ctx.initAsync().then(() => {
        const map = ctx.systems.map

        // Map emits 'draw' on full redraws, it's already throttled
        map.on("draw", () => {
            // Skip during introduction
            if (ctx.inIntro) return

            const [lon, lat] = map.center()
            const zoom = map.zoom()
            window.parent.postMessage(
                { type: "mapState", state: { lon, lat, zoom } },
                parentOrigin,
            )
        })
    })
})
