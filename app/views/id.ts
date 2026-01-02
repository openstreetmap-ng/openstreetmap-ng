import "./id.scss"
import "iD/dist/iD.css"
import "iD"

import { API_URL, ID_PATH, primaryLanguage } from "@lib/config"
import { parentLoadSystemApp } from "@lib/system-app"
import { assertExists } from "@std/assert"
import { throttle } from "@std/async/unstable-throttle"

const container = document.querySelector("div.id-container")
assertExists(container, "iD container not found")

parentLoadSystemApp((accessToken, parentOrigin) => {
  // @ts-expect-error
  const ctx = window.iD.coreContext()
  ctx.connection().apiConnections([])
  ctx.preauth({
    url: parentOrigin,
    apiUrl: API_URL,
    access_token: accessToken,
  })

  const id = ctx
    .embed(true)
    .assetPath(ID_PATH)
    .locale(primaryLanguage)
    .containerNode(container)
    .init()

  const map = id.map()

  // On map move, send the new state to the parent
  map.on(
    "move.embed",
    throttle(
      () => {
        // Skip during introduction
        if (id.inIntro()) return

        const [lon, lat] = map.center()
        const zoom = map.zoom()
        window.parent.postMessage(
          { type: "mapState", source: "id", state: { lon, lat, zoom } },
          parentOrigin,
        )
      },
      250,
      { ensureLastCall: true },
    ),
  )
})
