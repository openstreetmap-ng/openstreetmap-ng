import { encodeMapState, type MapState, parseLonLatZoom } from "@lib/map/state"
import { mount } from "@lib/mount"
import { qsEncode, qsParse } from "@lib/qs"
import { HOUR, MINUTE, SECOND } from "@std/datetime/constants"

mount("welcome-body", (body) => {
  const noteLink = body.querySelector("a.note-link")!
  const startButton = body.querySelector("a.start-btn")!

  // Support default location setting via URL parameters
  let providedState: MapState | undefined
  const params = qsParse(window.location.search)
  params.zoom ??= "17"
  params.layers ??= ""

  const at = parseLonLatZoom(params)
  if (at) providedState = { ...at, layersCode: params.layers }

  // Assign position only if it's valid
  let noteHref = "/note/new"
  if (providedState) noteHref += encodeMapState(providedState)
  noteLink.href = noteHref

  // Passthrough supported parameters
  const startParams: Record<string, string> = {}
  if (params.editor) startParams.editor = params.editor

  // If location was provided, redirect to /edit with the provided coordinates
  if (providedState) {
    startButton.href = `/edit${qsEncode(startParams)}${encodeMapState(providedState)}`
    return
  }

  // If location was not provided, request navigator.geolocation

  const onStartButtonClick = (e: Event) => {
    e.preventDefault()
    navigator.geolocation.getCurrentPosition(
      (position: GeolocationPosition) => {
        onGeolocationSuccess(position)
        window.location.href = startButton.href
      },
      () => {
        onGeolocationFailure()
        window.location.href = startButton.href
      },
      {
        maximumAge: 8 * HOUR,
        timeout: 10 * SECOND,
      },
    )
  }
  startButton.addEventListener("click", onStartButtonClick, { once: true })

  /** On geolocation success, redirect to /edit with the returned coordinates */
  const onGeolocationSuccess = (position: GeolocationPosition) => {
    console.debug("Welcome: Geolocation success", position)
    const lon = position.coords.longitude
    const lat = position.coords.latitude
    const zoom = 17
    const geolocationState = {
      lon,
      lat,
      zoom,
      layersCode: params.layers,
    } satisfies MapState

    startButton.href = `/edit${qsEncode(startParams)}${encodeMapState(geolocationState)}`
    startButton.removeEventListener("click", onStartButtonClick)
  }

  /** On geolocation failure, remove event listener */
  const onGeolocationFailure = () => {
    console.debug("Welcome: Geolocation failure")
    startButton.removeEventListener("click", onStartButtonClick)
  }

  /** If permission was granted, start geolocation early */
  const checkGeolocationPermission = async () => {
    const result = await navigator.permissions?.query({ name: "geolocation" })
    if (!result) return
    console.debug("Welcome: Geolocation permission", result.state)
    if (result.state === "granted") {
      navigator.geolocation.getCurrentPosition(
        onGeolocationSuccess,
        onGeolocationFailure,
        {
          maximumAge: 8 * HOUR,
          timeout: MINUTE,
        },
      )
    }
  }
  void checkGeolocationPermission()
})
