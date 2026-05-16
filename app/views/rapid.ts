import "@rapideditor/rapid"
import "@rapideditor/rapid/dist/rapid.css"
import "./rapid.scss"

import { parentLoadSystemApp } from "@runtime/system-app"
import { assertExists } from "@std/assert"
import { API_URL, primaryLanguage, RAPID_PATH } from "@utils/config"

const container = document.querySelector("div.rapid-container")
assertExists(container, "Rapid container not found")

parentLoadSystemApp(async (accessToken, parentOrigin) => {
  // @ts-expect-error
  const ctx = new window.Rapid.Context()
  ctx.preauth = {
    url: parentOrigin,
    apiUrl: API_URL,
    access_token: accessToken,
  }

  ctx.containerNode = container
  ctx.assetPath = RAPID_PATH
  ctx.locale = primaryLanguage
  ctx.embed(true)

  await ctx.initAsync()

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
