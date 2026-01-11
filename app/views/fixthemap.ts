import { encodeMapState, parseLonLatZoom } from "@lib/map/state"
import { mount } from "@lib/mount"
import { qsParse } from "@lib/qs"

mount("fixthemap-body", (body) => {
  const params = qsParse(window.location.search)
  let noteHref = "/note/new"

  // Supports default location setting via URL parameters
  params.zoom ??= "17"
  const at = parseLonLatZoom(params)
  if (at) noteHref += encodeMapState({ ...at, layersCode: params.layers })

  const noteLink = body.querySelector("a.note-link")!
  noteLink.href = noteHref
})
